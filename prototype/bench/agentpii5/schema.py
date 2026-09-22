"""AgentPII-RU v5 — the case format's v5 half: R01–R21 per case, K01–K15 per corpus.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_schema

WHAT THIS FILE IS. `contracts.CaseV5` is a shape; this is the only place that
says whether an instance of it is a case. Every rule of `contracts.V5_CASE_RULES`
and `contracts.V5_CORPUS_RULES` is implemented here, in that order, and each
problem is one string that STARTS WITH ITS RULE ID — a reviewer maps a line of
output to a line of the contract without reading this file.

EVERY PROBLEM, NEVER THE FIRST ONE ONLY. v4 learned it the expensive way: a
validator that stops at the first problem turns one authoring session into
twenty, and the generator's author starts guessing which rule bit next.

WHAT IS NOT RE-IMPLEMENTED. `v4.validate(case.base)` is CALLED (R02), never
copied: the trace tiling, the offset proof, the register gate and the
unlabelled-shape audit are v4's and must stay one definition. `v4.validate_
corpus` is NOT called — its band (330, 900) and its 5% clean cap are v4's
numbers, and v5 bands the corpus at `CORPUS_SIZE_BAND_V5` with clean at 10%
(spec §8.2). Calling it would refuse every v5 corpus for being v5.

K12 (the frozen holdout) IS NOT HERE and that is deliberate: it is a claim
about `ladder.json` on disk, not about a list of cases, so it lives in
`build.py` and is pinned by `test_build.test_holdout_frozen`. A corpus-level
validator that silently passed it would be the worse of the two options.

NOTHING HERE IMPORTS `pseudex` (`contracts.FORBIDDEN_IMPORT_PREFIX`).
"""
import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict

from bench.agentpii4 import schema as v4
from bench.agentpii4.schema import Case, PiiItem
from bench.agentpii5 import contracts as c
from bench.agentpii5.contracts import (BranchSpec, CaseV5, DocumentSpec, ForcedError, Hop,
                                       LoopSpec, MemorySpec, PickSpec, RagSpec,
                                       ReturnExpectation)

# The owners whose hop names a tool, from `contracts.Hop.tool_name`'s own
# comment. A constant rather than a literal in three checks: the comment is
# normative and a copy of it in three places is three copies that drift.
TOOL_BEARING_OWNERS: tuple[str, ...] = ("tool", "document", "tool_arg", "template", "summary")
# The two tools a `RagSpec` may name (`contracts.RagSpec.tool_name`'s comment).
RAG_TOOLS: tuple[str, ...] = ("kb_search", "doc_retrieve")
# The OUT owners that count as «the agent acted» in R15 (ruling R-31, and
# contracts' R15 text). `answer` is deliberately absent: showing the value
# again is what the agent already did at `show_turn`, and a loop whose whole
# act is a second sentence tested nothing. IMPORTED, never restated (F4.13):
# `metrics._transitions` decides what a chain is by the same tuple, and two
# copies of it would be one drift away from the corpus and the metric
# disagreeing about which OUT hops are acts.
ACTING_OUT_OWNERS: tuple[str, ...] = c.ACTING_OUT_OWNERS


def has_result(hops: Sequence[Hop]) -> bool:
    """The derived half of `CaseV5.has_result`: the loop reached a tool result
    AND an answer. Stored on the case because the ≥75% rule counts it over the
    whole corpus and a reader that recomputes it is a reader that can disagree."""
    return (any(hop.kind == "IN" and hop.owner == "tool" for hop in hops)
            and any(hop.kind == "OUT" and hop.owner == "answer" for hop in hops))


def _declared_return_forms() -> dict[str, tuple[str, ...]]:
    """Each tool's declared return forms, read off the landed registry.

    IMPORTED INSIDE THE FUNCTION, AND THERE IS NO «NOT YET» BRANCH ANY MORE.
    The import is lazy because `bench.agentpii5.tools` imports v4's registry and
    this module is imported by `scenarios5/common.py`, which `tools.py` does not
    need — a module-level import would make the two files a cycle. It is
    UNGUARDED because `tools.py` has landed: the earlier `find_spec` probe let
    R19 fall back to «the form is in the closed vocabulary», which is the weaker
    half of the rule, and a weaker check that nothing announces is the kind of
    silent fallback this repository refuses. A broken `tools.py` now raises here
    with its own traceback instead of quietly lowering the bar.
    """
    from bench.agentpii5.tools import REGISTRY_V5
    return {name: tuple(form.form for form in spec.return_forms)
            for name, spec in REGISTRY_V5.items()}


# --- per case: R01 … R21 ------------------------------------------------------

def validate_v5(case: CaseV5) -> list[str]:
    """Every rule of `contracts.V5_CASE_RULES` violated by this case.

    A NAME THAT MUST RESOLVE IS CHECKED WHERE IT IS DECLARED. R08 and R14 say
    so for hops and for `BranchSpec`; the same check is applied under R13, R15,
    R17 and R18 to the tools those specs name, because nothing else would catch
    a mistyped tool in a `PickSpec` and a spec naming a tool the case does not
    offer describes a call that cannot happen.
    """
    problems: list[str] = []
    base = case.base
    tag = base.id
    items: dict[str, PiiItem] = {item.id: item for item in base.pii}
    seed_ids: set[str] = {record.id for record in base.seed_records}
    hop_count = len(case.hops)

    # R01 behaviour in BEHAVIOURS
    if case.behaviour not in c.BEHAVIOURS:
        problems.append(f"R01 {tag}: unknown behaviour {case.behaviour!r}")

    # R02 v4.validate(base) reports nothing
    for problem in v4.validate(base):
        problems.append(f"R02 {problem}")

    # R03 hop indexes, kinds and owners
    for position, hop in enumerate(case.hops):
        if hop.hop_index != position:
            problems.append(f"R03 {tag}: hop at position {position} carries hop_index {hop.hop_index}")
        if hop.kind not in c.HOP_KINDS:
            problems.append(f"R03 {tag}: hop {position} has unknown kind {hop.kind!r}")
        elif hop.kind == "IN" and hop.owner not in c.IN_OWNERS:
            problems.append(f"R03 {tag}: hop {position} is IN with owner {hop.owner!r}, "
                            f"not one of {c.IN_OWNERS}")
        elif hop.kind == "OUT" and hop.owner not in c.OUT_OWNERS:
            problems.append(f"R03 {tag}: hop {position} is OUT with owner {hop.owner!r}, "
                            f"not one of {c.OUT_OWNERS}")
        if hop.owner not in c.HOP_OWNERS:
            problems.append(f"R03 {tag}: hop {position} has unknown owner {hop.owner!r}")

    # R04 every hop names an item and a user turn
    for hop in case.hops:
        if hop.item_id not in items:
            problems.append(f"R04 {tag}: hop {hop.hop_index} names item {hop.item_id!r}, "
                            f"which the case does not carry")
        if not 0 <= hop.turn < len(base.messages):
            problems.append(f"R04 {tag}: hop {hop.hop_index} points at message {hop.turn}")
        elif base.messages[hop.turn].role != "user":
            problems.append(f"R04 {tag}: hop {hop.hop_index} opens at message {hop.turn}, "
                            f"which is {base.messages[hop.turn].role}, not user")

    # R05 the locus an IN hop's owner implies, and the declared return behind it
    returning_tools: set[str] = {expectation.tool_name for expectation in case.returns}
    for hop in case.hops:
        if hop.kind != "IN":
            continue
        item = items.get(hop.item_id)
        if item is None:
            continue                              # already reported by R04
        if hop.owner == "user" and item.where.kind != "message":
            problems.append(f"R05 {tag}: IN/user hop {hop.hop_index} carries item {hop.item_id}, "
                            f"whose locus is {item.where.kind!r}, not a message")
        if hop.owner in ("tool", "document"):
            if item.where.kind != "seed":
                problems.append(f"R05 {tag}: IN/{hop.owner} hop {hop.hop_index} carries item "
                                f"{hop.item_id}, whose locus is {item.where.kind!r}, not a seed")
            if hop.tool_name not in returning_tools:
                problems.append(f"R05 {tag}: IN/{hop.owner} hop {hop.hop_index} reads "
                                f"{hop.tool_name!r}, which declares no ReturnExpectation")

    # R06 the chain link points BACK, at an IN hop of the same value or person
    for hop in case.hops:
        if hop.kind != "OUT" or hop.source_hop == -1:
            continue
        if not 0 <= hop.source_hop < hop.hop_index or hop.source_hop >= hop_count:
            problems.append(f"R06 {tag}: hop {hop.hop_index} sources hop {hop.source_hop}, "
                            f"which is not an earlier hop")
            continue
        source = case.hops[hop.source_hop]
        if source.kind != "IN":
            problems.append(f"R06 {tag}: hop {hop.hop_index} sources hop {hop.source_hop}, "
                            f"which is {source.kind}, not IN")
            continue
        if source.item_id == hop.item_id:
            continue
        here, there = items.get(hop.item_id), items.get(source.item_id)
        if here is None or there is None or here.identity != there.identity:
            problems.append(f"R06 {tag}: hop {hop.hop_index} ({hop.item_id}) sources hop "
                            f"{hop.source_hop} ({source.item_id}), another person's value")

    # R07 has_result is derived, stored, and buys the minimal loop
    derived = has_result(case.hops)
    if case.has_result != derived:
        problems.append(f"R07 {tag}: has_result is {case.has_result}, the hops say {derived}")
    if case.has_result and hop_count < c.MIN_HOPS_WITH_RESULT:
        problems.append(f"R07 {tag}: a case with a result carries {hop_count} hops, "
                        f"the minimal loop is {c.MIN_HOPS_WITH_RESULT}")

    # R08 a tool-bearing hop names an offered tool and an ordinal; nothing else does
    for hop in case.hops:
        bears = hop.owner in TOOL_BEARING_OWNERS
        if bears and hop.tool_name not in base.tools:
            problems.append(f"R08 {tag}: hop {hop.hop_index} names tool {hop.tool_name!r}, "
                            f"which the case does not offer")
        if not bears and hop.tool_name:
            problems.append(f"R08 {tag}: hop {hop.hop_index} has owner {hop.owner!r} "
                            f"yet names tool {hop.tool_name!r}")
        if (hop.call_ordinal >= 0) != bool(hop.tool_name):
            problems.append(f"R08 {tag}: hop {hop.hop_index} has call_ordinal "
                            f"{hop.call_ordinal} with tool {hop.tool_name!r}")

    # R09 a parallel group is ≥ 2 OUT hops of ONE turn, and only `parallel` has one
    groups: dict[str, list[Hop]] = {}
    for hop in case.hops:
        if hop.parallel_group:
            groups.setdefault(hop.parallel_group, []).append(hop)
    for label in sorted(groups):
        group = groups[label]
        if any(hop.kind != "OUT" for hop in group):
            problems.append(f"R09 {tag}: parallel group {label!r} holds an IN hop")
        if len({hop.turn for hop in group}) != 1:
            problems.append(f"R09 {tag}: parallel group {label!r} spans turns "
                            f"{sorted({hop.turn for hop in group})}")
        if len(group) < 2:
            problems.append(f"R09 {tag}: parallel group {label!r} holds one hop")
    if bool(groups) != (case.behaviour == "parallel"):
        problems.append(f"R09 {tag}: behaviour {case.behaviour!r} with "
                        f"{len(groups)} parallel groups")

    # R10 a forced error is what makes a retry deterministic
    if bool(case.forced) != (case.behaviour == "retry_same_tool"):
        problems.append(f"R10 {tag}: behaviour {case.behaviour!r} with "
                        f"{len(case.forced)} forced errors")
    for forced in case.forced:
        if forced.tool_name not in base.tools:
            problems.append(f"R10 {tag}: forced error names tool {forced.tool_name!r}, "
                            f"which the case does not offer")
        if forced.echo_item_id not in items:
            problems.append(f"R10 {tag}: forced error echoes item {forced.echo_item_id!r}, "
                            f"which the case does not carry")
        if forced.message_template.count("{value}") != 1:
            problems.append(f"R10 {tag}: forced error template has "
                            f"{forced.message_template.count('{value}')} value slots, needs one")
        if not any(hop.tool_name == forced.tool_name and hop.call_ordinal == forced.call_ordinal + 1
                   for hop in case.hops):
            problems.append(f"R10 {tag}: nothing calls {forced.tool_name!r} again after the "
                            f"forced error on ordinal {forced.call_ordinal}")

    # R11 two targets of ONE tool
    if case.behaviour == "same_tool_other_target":
        by_tool: dict[str, set[str]] = {}
        for hop in case.hops:
            if hop.kind == "OUT" and hop.owner == "tool_arg" and hop.item_id in items:
                by_tool.setdefault(hop.tool_name, set()).add(items[hop.item_id].identity)
        if not any(len(identities) >= 2 for identities in by_tool.values()):
            problems.append(f"R11 {tag}: no tool carries OUT hops of two identities")

    # R12 the chain: an argument of B fed by a result of A
    if case.behaviour == "sequential_chain":
        chained = False
        for hop in case.hops:
            if hop.kind != "OUT" or not hop.tool_name or not 0 <= hop.source_hop < hop_count:
                continue
            source = case.hops[hop.source_hop]
            if source.kind == "IN" and source.owner == "tool" and source.tool_name != hop.tool_name:
                chained = True
        if not chained:
            problems.append(f"R12 {tag}: no OUT hop is fed by the result of ANOTHER tool")

    # R13 fan-out: candidates that a placeholder masker cannot tell apart
    if (case.pick is not None) != (case.behaviour == "fanout_pick"):
        problems.append(f"R13 {tag}: behaviour {case.behaviour!r} with "
                        f"pick {'set' if case.pick is not None else 'unset'}")
    if case.pick is not None:
        problems.extend(_pick_problems(tag, base, case.pick))

    # R14 branching: two different offered tools
    if (case.branch is not None) != (case.behaviour == "branching"):
        problems.append(f"R14 {tag}: behaviour {case.behaviour!r} with "
                        f"branch {'set' if case.branch is not None else 'unset'}")
    if case.branch is not None:
        problems.extend(_branch_problems(tag, base, case.branch))

    # R15 user in the loop: show, confirm WITHOUT the value, then act
    if (case.loop is not None) != (case.behaviour == "user_in_loop"):
        problems.append(f"R15 {tag}: behaviour {case.behaviour!r} with "
                        f"loop {'set' if case.loop is not None else 'unset'}")
    if case.loop is not None:
        problems.extend(_loop_problems(tag, base, case.loop, case.hops))

    # R16 memory and anaphora
    if case.behaviour == "memory_anaphora" and not case.memory:
        problems.append(f"R16 {tag}: behaviour memory_anaphora with no MemorySpec")
    for spec in case.memory:
        problems.extend(_memory_problems(tag, base, items, spec))

    # R17 RAG: k chunks, at least one of them another person's
    if (case.rag is not None) != (case.behaviour == "rag"):
        problems.append(f"R17 {tag}: behaviour {case.behaviour!r} with "
                        f"rag {'set' if case.rag is not None else 'unset'}")
    if case.rag is not None:
        problems.extend(_rag_problems(tag, base, items, seed_ids, case.rag))

    # R18 documents
    if (case.document is not None) != (case.behaviour == "document"):
        problems.append(f"R18 {tag}: behaviour {case.behaviour!r} with "
                        f"document {'set' if case.document is not None else 'unset'}")
    if case.document is not None:
        problems.extend(_document_problems(tag, base, items, seed_ids, case.document))

    # R19 the declared returns
    declared = _declared_return_forms()
    for expectation in case.returns:
        problems.extend(_return_problems(tag, base, items, expectation, declared))

    # R20 streaming is a voice axis
    if case.streaming and base.register not in c.SPEECH_REGISTERS:
        problems.append(f"R20 {tag}: streaming case in register {base.register!r}, "
                        f"not one of {c.SPEECH_REGISTERS}")

    # R21 the OUT owner of a leaf is the closed table's answer, both ways.
    # BOTH WAYS ON PURPOSE: the owner decides which `form_hOUT` line a hop
    # counts in, so a `notify_sms.text` leaf declared as `tool_arg` is not a
    # smaller mistake than a `crm_upsert_contact.contact.phone` leaf declared
    # as `template` — each moves a hop into a line it does not belong to.
    for hop in case.hops:
        if hop.kind != "OUT" or hop.owner not in TOOL_BEARING_OWNERS:
            continue
        expected = c.hop_owner_of_leaf(hop.tool_name, hop.path)
        if expected != hop.owner:
            problems.append(f"R21 {tag}: hop {hop.hop_index} on {hop.tool_name}.{hop.path} "
                            f"is owner {hop.owner!r}, the table says {expected!r}")
    return problems


def _pick_problems(tag: str, base: Case, pick: PickSpec) -> list[str]:
    """R13's body. A candidate without a value of the TARGET's type is not a
    candidate: the family exists to make the agent match by value, and a
    candidate it can tell apart by shape alone tests nothing."""
    problems: list[str] = []
    for role, name in (("list_tool", pick.list_tool), ("act_tool", pick.act_tool)):
        if name not in base.tools:
            problems.append(f"R13 {tag}: pick.{role} {name!r} is not offered")
    if len(set(pick.candidate_identities)) < 2:
        problems.append(f"R13 {tag}: pick names {len(set(pick.candidate_identities))} "
                        f"candidate identities, needs two")
    if pick.target_identity not in pick.candidate_identities:
        problems.append(f"R13 {tag}: pick target {pick.target_identity!r} is not a candidate")
    target_types = {item.type for item in base.pii
                    if item.identity == pick.target_identity and item.where.kind == "seed"}
    if not target_types:
        problems.append(f"R13 {tag}: pick target {pick.target_identity!r} has no seed item "
                        f"to be matched by")
    for candidate in pick.candidate_identities:
        types = {item.type for item in base.pii
                 if item.identity == candidate and item.where.kind == "seed"}
        if not types & target_types:
            problems.append(f"R13 {tag}: candidate {candidate!r} carries no seed item of the "
                            f"target's types {sorted(target_types)}")
    return problems


def _branch_problems(tag: str, base: Case, branch: BranchSpec) -> list[str]:
    """R14's body."""
    problems: list[str] = []
    for role, name in (("probe_tool", branch.probe_tool), ("then_tool", branch.then_tool),
                       ("else_tool", branch.else_tool)):
        if name not in base.tools:
            problems.append(f"R14 {tag}: branch.{role} {name!r} is not offered")
    if branch.then_tool == branch.else_tool:
        problems.append(f"R14 {tag}: both branches call {branch.then_tool!r}; "
                        f"a branch the agent cannot get wrong measures nothing")
    if branch.seed_present != bool(base.seed_records):
        problems.append(f"R14 {tag}: branch.seed_present is {branch.seed_present} while the "
                        f"case carries {len(base.seed_records)} seed records")
    return problems


def _loop_problems(tag: str, base: Case, loop: LoopSpec, hops: Sequence[Hop]) -> list[str]:
    """R15's body.

    THE ACT IS NOT ONLY A TOOL ARGUMENT (ruling R-31). A handover — «передаю
    оператору», `escalate_to_human`, `crm_add_note` — acts through a SUMMARY
    leaf, and a template message through a TEMPLATE leaf; demanding
    `owner == "tool_arg"` refused those loops for writing the confirmed value
    into the field the tool actually has.

    THE ACT IS AT OR AFTER THE CONFIRMING TURN, NOT STRICTLY AFTER IT. A hop's
    `turn` is the user message that OPENS the turn it happens in, and the act
    that follows «да, это я» happens inside the turn that message opened — so a
    strict `>` would refuse the two-message loop the spec's own row describes
    («найти → показать → подтвердить → действовать») and demand a third user
    message that says nothing.
    """
    problems: list[str] = []
    for role, name in (("find_tool", loop.find_tool), ("act_tool", loop.act_tool)):
        if name not in base.tools:
            problems.append(f"R15 {tag}: loop.{role} {name!r} is not offered")
    if not loop.show_turn < loop.confirm_turn:
        problems.append(f"R15 {tag}: show_turn {loop.show_turn} is not before "
                        f"confirm_turn {loop.confirm_turn}")
    for item in base.pii:
        if item.value and item.value in loop.confirm_phrase:
            problems.append(f"R15 {tag}: confirm_phrase carries item {item.id} "
                            f"({item.value!r}); a confirmation that repeats the value "
                            f"tests no memory")
    if not any(hop.kind == "OUT" and hop.owner == "answer" and hop.turn == loop.show_turn
               for hop in hops):
        problems.append(f"R15 {tag}: no OUT/answer hop at show_turn {loop.show_turn}")
    if not any(hop.kind == "OUT" and hop.owner in ACTING_OUT_OWNERS
               and hop.turn >= loop.confirm_turn for hop in hops):
        problems.append(f"R15 {tag}: no OUT hop with owner in {ACTING_OUT_OWNERS} at or after "
                        f"confirm_turn {loop.confirm_turn}")
    return problems


def _memory_problems(tag: str, base: Case, items: dict[str, PiiItem],
                     spec: MemorySpec) -> list[str]:
    """R16's body.

    «NOT WRITTEN AGAIN» IS CHECKED BY VALUE, NOT BY ITEM ID. A second writing
    of the same value is a different `PiiItem`, so an id check would pass the
    very case the rule forbids — «пришлите ему, Иванову Петру, счёт» said at
    the recall turn while the spec claims a pronoun.
    """
    problems: list[str] = []
    item = items.get(spec.item_id)
    if item is None:
        problems.append(f"R16 {tag}: MemorySpec names item {spec.item_id!r}, "
                        f"which the case does not carry")
        return problems
    if spec.anaphora not in c.ANAPHORA_KINDS:
        problems.append(f"R16 {tag}: MemorySpec anaphora {spec.anaphora!r} is not "
                        f"one of {c.ANAPHORA_KINDS}")
    if not spec.first_turn < spec.recall_turn:
        problems.append(f"R16 {tag}: MemorySpec first_turn {spec.first_turn} is not before "
                        f"recall_turn {spec.recall_turn}")
    for role, turn in (("first_turn", spec.first_turn), ("recall_turn", spec.recall_turn)):
        if not 0 <= turn < len(base.messages) or base.messages[turn].role != "user":
            problems.append(f"R16 {tag}: MemorySpec {role} {turn} is not a user message")
    if spec.anaphora != "none":
        for other in base.pii:
            if (other.where.kind == "message" and other.where.msg == spec.recall_turn
                    and other.value == item.value):
                problems.append(f"R16 {tag}: {spec.anaphora!r} recall at turn "
                                f"{spec.recall_turn} writes {item.value!r} again "
                                f"(item {other.id})")
    return problems


def _rag_problems(tag: str, base: Case, items: dict[str, PiiItem], seed_ids: set[str],
                  rag: RagSpec) -> list[str]:
    """R17's body."""
    problems: list[str] = []
    if rag.tool_name not in RAG_TOOLS:
        problems.append(f"R17 {tag}: rag.tool_name {rag.tool_name!r} is not one of {RAG_TOOLS}")
    if rag.tool_name not in base.tools:
        problems.append(f"R17 {tag}: rag.tool_name {rag.tool_name!r} is not offered")
    if rag.k != len(rag.chunk_ids):
        problems.append(f"R17 {tag}: rag.k is {rag.k}, chunk_ids hold {len(rag.chunk_ids)}")
    for chunk_id in rag.chunk_ids:
        if chunk_id not in seed_ids:
            problems.append(f"R17 {tag}: chunk {chunk_id!r} is not a seed record")
    chunk_identities = {item.identity for item in base.pii
                        if item.where.kind == "seed" and item.where.record in rag.chunk_ids}
    if not rag.foreign_identities:
        problems.append(f"R17 {tag}: rag declares no foreign identity; the family exists "
                        f"to measure keeping other people apart")
    for identity in rag.foreign_identities:
        if identity == base.expects.primary_identity:
            problems.append(f"R17 {tag}: foreign identity {identity!r} is the customer")
        if identity not in chunk_identities:
            problems.append(f"R17 {tag}: foreign identity {identity!r} is in no chunk")
    for item_id in rag.query_item_ids:
        if item_id not in items:
            problems.append(f"R17 {tag}: query item {item_id!r} is not an item of the case")
    return problems


def _document_problems(tag: str, base: Case, items: dict[str, PiiItem], seed_ids: set[str],
                       document: DocumentSpec) -> list[str]:
    """R18's body.

    «SEED ITEMS OF THE DOCUMENT'S RECORDS» IS NOW CHECKED AGAINST THE RECORDS
    (ruling R-30). `DocumentSpec.record_ids` names the rows the document is
    rendered from, so an extracted item that lives in ANOTHER record — the
    caller's own CRM card, say, which the agent never read out of the file — is
    refused here instead of counting as a document extraction nobody made.

    `record_count` COUNTS PEOPLE AND `record_ids` COUNTS ROWS. A CSV is one
    `documents` row holding two or three people, so the equality R-11 first
    asked for would have refused every CSV case in the corpus; the floor on
    `record_count` is what keeps «several people in one payload» a real claim.
    """
    problems: list[str] = []
    if document.format not in c.DOCUMENT_FORMATS:
        problems.append(f"R18 {tag}: document format {document.format!r} is not "
                        f"one of {c.DOCUMENT_FORMATS}")
    if document.read_tool not in base.tools:
        problems.append(f"R18 {tag}: document.read_tool {document.read_tool!r} is not offered")
    if document.extract_to_tool not in base.tools:
        problems.append(f"R18 {tag}: document.extract_to_tool {document.extract_to_tool!r} "
                        f"is not offered")
    floor = 2 if document.format == "csv" else 1
    if document.record_count < floor:
        problems.append(f"R18 {tag}: a {document.format} document carries "
                        f"{document.record_count} records, needs {floor}")
    if not document.record_ids:
        problems.append(f"R18 {tag}: document names no seed record; nothing renders it")
    for record_id in document.record_ids:
        if record_id not in seed_ids:
            problems.append(f"R18 {tag}: document record {record_id!r} is not a seed record")
    if not document.extracted_item_ids:
        problems.append(f"R18 {tag}: document extracts nothing; there is no OUT hop to count")
    for item_id in document.extracted_item_ids:
        item = items.get(item_id)
        if item is None:
            problems.append(f"R18 {tag}: extracted item {item_id!r} is not an item of the case")
        elif item.where.kind != "seed":
            problems.append(f"R18 {tag}: extracted item {item_id} has locus "
                            f"{item.where.kind!r}; a document's value is a seed")
        elif item.where.record not in document.record_ids:
            problems.append(f"R18 {tag}: extracted item {item_id} lives in record "
                            f"{item.where.record!r}, which the document does not render "
                            f"({document.record_ids})")
    return problems


def _return_problems(tag: str, base: Case, items: dict[str, PiiItem],
                     expectation: ReturnExpectation,
                     declared: dict[str, tuple[str, ...]]) -> list[str]:
    """R19's body.

    THE FORM IS CHECKED AGAINST THE TOOL, NOT ONLY AGAINST THE VOCABULARY. A
    tool declares EVERY form it can return — a state-decided one
    (`address_suggest` canon/list, `bank_client_find` single/list/empty) is
    declared as all of them — and the case names the one THIS seeded state
    yields (ruling R-17). Whether the seeding really produces it is not
    knowable from the case alone; the harness records the mock's ACTUAL form
    and `build.py --check` prints the disagreement as a corpus defect."""
    problems: list[str] = []
    if expectation.tool_name not in base.tools:
        problems.append(f"R19 {tag}: return of {expectation.tool_name!r}, "
                        f"which the case does not offer")
    if expectation.return_form not in c.RETURN_FORMS:
        problems.append(f"R19 {tag}: return form {expectation.return_form!r} is not "
                        f"one of {c.RETURN_FORMS}")
    else:
        forms = declared.get(expectation.tool_name)
        if forms is None:
            problems.append(f"R19 {tag}: {expectation.tool_name!r} has no ToolSpecV5")
        elif expectation.return_form not in forms:
            problems.append(f"R19 {tag}: {expectation.tool_name!r} does not declare return "
                            f"form {expectation.return_form!r}; it declares {forms}")
    for item_id in expectation.result_item_ids:
        item = items.get(item_id)
        if item is None:
            problems.append(f"R19 {tag}: result item {item_id!r} is not an item of the case")
        elif item.where.kind != "seed":
            problems.append(f"R19 {tag}: result item {item_id} has locus {item.where.kind!r}; "
                            f"a tool returns what the backend holds")
    return problems


# --- per corpus: K01 … K15 ----------------------------------------------------

def validate_corpus_v5(cases: Sequence[CaseV5], registry_names: tuple[str, ...]) -> list[str]:
    """Every rule of `contracts.V5_CORPUS_RULES` the corpus violates.

    K02 IS A FLOOR AND NOT A CEILING, and the difference is the whole point of
    §8.2: `single` and `sequential_chain` are supplied by the revised v4 corpus
    and overshoot their shares by design, while a family BELOW its floor has
    lost the statistical power the spec bought it. A two-sided band would
    refuse the corpus for the one thing that costs nothing.

    K12 is not here — see this module's docstring.
    """
    problems: list[str] = []
    total = len(cases)
    if total == 0:
        return ["K01 the corpus is empty"]

    # K01 size (and the identity of a case: two cases under one id are one case
    # counted twice in every share below, which no other rule would catch)
    low, high = c.CORPUS_SIZE_BAND_V5
    if not low <= total <= high:
        problems.append(f"K01 corpus holds {total} cases, band is {c.CORPUS_SIZE_BAND_V5}")
    ids = [case.base.id for case in cases]
    if len(set(ids)) != len(ids):
        duplicates = sorted({one for one in ids if ids.count(one) > 1})
        problems.append(f"K01 duplicate case ids: {duplicates[:8]}")

    # K02 every behaviour at its floor, and no ceiling
    counts: dict[str, int] = {}
    for case in cases:
        counts[case.behaviour] = counts.get(case.behaviour, 0) + 1
    for behaviour in c.BEHAVIOURS:
        seen = counts.get(behaviour, 0)
        floor = c.BEHAVIOUR_FLOORS[behaviour]
        if seen < floor:
            problems.append(f"K02 behaviour {behaviour!r}: {seen} cases, floor {floor}")
        share = seen / total
        want = c.BEHAVIOUR_SHARES[behaviour] - c.SHARE_TOLERANCE
        if share < want:
            problems.append(f"K02 behaviour {behaviour!r}: share {share:.1%}, "
                            f"floor {want:.1%}")

    # K03 the tool result is the base loop
    with_result = sum(1 for case in cases if case.has_result) / total
    if with_result < c.MIN_SHARE_WITH_RESULT:
        problems.append(f"K03 {with_result:.1%} of cases reach a tool result, "
                        f"floor {c.MIN_SHARE_WITH_RESULT:.0%}")

    # K04 the register mix of the v5-AUTHORED cases, voice as one bucket.
    #
    # THE 834 REVISED CASES ARE NOT IN THIS COUNT, and that is ruling R-09
    # rather than a convenience. v4 measured voice_raw 276 / voice_itn 183 /
    # chat 250 / sloppy 119 / clean 6 and those bytes are frozen — a corpus-wide
    # K04 would be a claim about a block no v5 decision can move, so it would be
    # red at every feasible corpus size (clean alone would need ≈ 1 750 authored
    # cases, far outside CORPUS_SIZE_BAND_V5) and the only way to satisfy it
    # would be to stop keeping v4 whole. `build.py --check` prints the
    # corpus-wide table beside the authored one so nobody reads this share as
    # the whole corpus's.
    authored = [case for case in cases if not case.revised_from_v4]
    if not authored:
        problems.append("K04 no v5-authored case: the register mix is a claim about what v5 "
                        "writes, and a corpus of revised cases alone makes none")
    else:
        registers: dict[str, int] = {}
        for case in authored:
            registers[case.base.register] = registers.get(case.base.register, 0) + 1
        seen_registers = {"voice": sum(registers.get(name, 0) for name in c.SPEECH_REGISTERS)}
        for name in c.REGISTERS:
            if name not in c.SPEECH_REGISTERS:
                seen_registers[name] = registers.get(name, 0)
        for name, want in c.REGISTER_SHARES.items():
            share = seen_registers.get(name, 0) / len(authored)
            if abs(share - want) > c.SHARE_TOLERANCE + 1e-9:
                problems.append(f"K04 register {name!r} of the {len(authored)} authored cases: "
                                f"share {share:.1%}, want {want:.0%} ± {c.SHARE_TOLERANCE:.0%}")

    # K05 the two types v4 never carried
    for kind, floor in c.MIN_CASES_BY_TYPE.items():
        carrying = sum(1 for case in cases if any(item.type == kind for item in case.base.pii))
        if carrying < floor:
            problems.append(f"K05 type {kind}: {carrying} cases carry it, floor {floor}")

    # K06 no type below v4's item count
    per_type: dict[str, int] = {}
    for case in cases:
        for item in case.base.pii:
            per_type[item.type] = per_type.get(item.type, 0) + 1
    for kind, floor in c.V4_TYPE_ITEM_COUNTS.items():
        seen = per_type.get(kind, 0)
        if seen < floor:
            problems.append(f"K06 type {kind}: {seen} items, v4 had {floor}")

    # K07 every tool reachable often enough to have a denominator
    reach: dict[str, int] = {}
    for case in cases:
        for name in case.base.expects.reachable_tools:
            reach[name] = reach.get(name, 0) + 1
    for name in registry_names:
        if reach.get(name, 0) < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"K07 tool {name!r} reachable in {reach.get(name, 0)} cases, "
                            f"below {c.MIN_TYPE_DENOMINATOR}")

    # K08 clusters the bootstrap can resample
    clusters: dict[str, int] = {}
    for case in cases:
        clusters[case.base.cluster] = clusters.get(case.base.cluster, 0) + 1
    multi = sum(1 for size in clusters.values() if size >= 3)
    if multi < c.MIN_CLUSTER_MULTI:
        problems.append(f"K08 {multi} clusters of size ≥ 3, need {c.MIN_CLUSTER_MULTI}")

    # K09 both ways of naming a conversation
    explicit = sum(1 for case in cases if case.base.conversation_id)
    if explicit == 0 or explicit == total:
        problems.append(f"K09 {explicit} of {total} cases name a conversation id; "
                        f"both explicit and derived must occur")

    # K10 the v4 corpus is kept whole
    revised = [case for case in cases if case.revised_from_v4]
    if len(revised) != c.V4_CORPUS_SIZE:
        problems.append(f"K10 {len(revised)} revised v4 cases, v4 has {c.V4_CORPUS_SIZE}")
    with_loop = sum(1 for case in revised if case.has_result)
    if with_loop != c.V4_CASES_WITH_RESULT:
        problems.append(f"K10 {with_loop} revised cases reach a result, "
                        f"v4 has {c.V4_CASES_WITH_RESULT} with seeds")

    # K11 streaming
    streaming = sum(1 for case in cases if case.streaming)
    if streaming < c.MIN_STREAMING_CASES:
        problems.append(f"K11 {streaming} streaming cases, floor {c.MIN_STREAMING_CASES}")

    # K13 every owner has a denominator, and the rarer ones span behaviours
    owner_cases: dict[str, int] = {}
    owner_behaviours: dict[str, set[str]] = {}
    for case in cases:
        for owner in {hop.owner for hop in case.hops}:
            owner_cases[owner] = owner_cases.get(owner, 0) + 1
            owner_behaviours.setdefault(owner, set()).add(case.behaviour)
    for owner in c.HOP_OWNERS:
        seen = owner_cases.get(owner, 0)
        if seen < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"K13 owner {owner!r} declared by {seen} cases, "
                            f"below {c.MIN_TYPE_DENOMINATOR}")
        if owner in ("user", "tool_arg"):
            continue
        spread = len(owner_behaviours.get(owner, set()))
        if spread < 2:
            problems.append(f"K13 owner {owner!r} appears in {spread} behaviours, needs 2")

    # K14 the shapes inside the two new families
    document_cases = [case for case in cases if case.document is not None]
    for fmt in c.DOCUMENT_FORMATS:
        seen = sum(1 for case in document_cases if case.document is not None
                   and case.document.format == fmt)
        if seen < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"K14 document format {fmt!r} in {seen} cases, "
                            f"below {c.MIN_TYPE_DENOMINATOR}")
    memory_cases = [case for case in cases if case.memory]
    for kind in c.ANAPHORA_KINDS:
        if kind == "none":
            continue
        seen = sum(1 for case in memory_cases
                   if any(spec.anaphora == kind for spec in case.memory))
        if seen < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"K14 anaphora {kind!r} in {seen} cases, "
                            f"below {c.MIN_TYPE_DENOMINATOR}")
    long_memory = sum(1 for case in memory_cases if _is_long_memory_case(case))
    if long_memory < c.MIN_TYPE_DENOMINATOR:
        problems.append(f"K14 {long_memory} cases carry ≥ 3 MemorySpecs over ≥ 2 identities "
                        f"and ≥ 5 user turns, below {c.MIN_TYPE_DENOMINATOR}")

    # K15 many records of ONE person in one result
    many = sum(1 for case in cases if _has_multi_record_return(case))
    if many < c.MIN_TYPE_DENOMINATOR:
        problems.append(f"K15 {many} cases return ≥ 2 items of one identity in one call, "
                        f"below {c.MIN_TYPE_DENOMINATOR}")
    return problems


def _is_long_memory_case(case: CaseV5) -> bool:
    """K14's third clause: ≥ 3 MemorySpecs, ≥ 2 identities among their items,
    ≥ 5 user turns in the dialogue."""
    if len(case.memory) < 3:
        return False
    items = {item.id: item for item in case.base.pii}
    identities = {items[spec.item_id].identity for spec in case.memory if spec.item_id in items}
    turns = sum(1 for message in case.base.messages if message.role == "user")
    return len(identities) >= 2 and turns >= 5


def _has_multi_record_return(case: CaseV5) -> bool:
    """K15: ONE call whose result carries ≥ 2 items of ONE identity."""
    items = {item.id: item for item in case.base.pii}
    for expectation in case.returns:
        per_identity: dict[str, int] = {}
        for item_id in expectation.result_item_ids:
            item = items.get(item_id)
            if item is None:
                continue
            per_identity[item.identity] = per_identity.get(item.identity, 0) + 1
        if any(count >= 2 for count in per_identity.values()):
            return True
    return False


# --- serialisation -------------------------------------------------------------

def case_v5_to_json(case: CaseV5) -> dict[str, object]:
    """The v5 snapshot of one case. `base` goes through v4's own `to_json`, so
    `corpus.json` (the v4 view every v4 reader opens) and `corpus.v5.json` carry
    the SAME bytes for the v4 half — a baseline written twice is a baseline that
    can drift from the treatment."""
    return {
        "base": case.base.to_json(),
        "behaviour": case.behaviour,
        "hops": [asdict(hop) for hop in case.hops],
        "returns": [asdict(one) for one in case.returns],
        "forced": [asdict(one) for one in case.forced],
        "memory": [asdict(one) for one in case.memory],
        "pick": asdict(case.pick) if case.pick is not None else None,
        "branch": asdict(case.branch) if case.branch is not None else None,
        "loop": asdict(case.loop) if case.loop is not None else None,
        "rag": asdict(case.rag) if case.rag is not None else None,
        "document": asdict(case.document) if case.document is not None else None,
        "has_result": case.has_result,
        "streaming": case.streaming,
        "revised_from_v4": case.revised_from_v4,
    }


def case_v5_from_json(raw: dict[str, object]) -> CaseV5:
    """The inverse. Sequences come back as TUPLES: `CaseV5` is frozen and a
    list inside it would make two equal cases compare unequal after a round
    trip, which is exactly what `corpus_digest_v5` would then disagree about."""
    pick = raw["pick"]
    branch = raw["branch"]
    loop = raw["loop"]
    rag = raw["rag"]
    document = raw["document"]
    return CaseV5(
        base=v4.case_from_json(raw["base"]),  # type: ignore[arg-type]
        behaviour=str(raw["behaviour"]),
        hops=tuple(Hop(**one) for one in raw["hops"]),  # type: ignore[union-attr]
        returns=tuple(ReturnExpectation(
            tool_name=str(one["tool_name"]), call_ordinal=int(one["call_ordinal"]),
            return_form=str(one["return_form"]),
            result_item_ids=tuple(one["result_item_ids"]))
            for one in raw["returns"]),  # type: ignore[union-attr]
        forced=tuple(ForcedError(**one) for one in raw["forced"]),  # type: ignore[union-attr]
        memory=tuple(MemorySpec(**one) for one in raw["memory"]),  # type: ignore[union-attr]
        pick=None if pick is None else PickSpec(
            list_tool=str(pick["list_tool"]),  # type: ignore[index]
            candidate_identities=tuple(pick["candidate_identities"]),  # type: ignore[index]
            target_identity=str(pick["target_identity"]),  # type: ignore[index]
            act_tool=str(pick["act_tool"])),  # type: ignore[index]
        branch=None if branch is None else BranchSpec(**branch),  # type: ignore[arg-type]
        loop=None if loop is None else LoopSpec(**loop),  # type: ignore[arg-type]
        rag=None if rag is None else RagSpec(
            tool_name=str(rag["tool_name"]), k=int(rag["k"]),  # type: ignore[index]
            chunk_ids=tuple(rag["chunk_ids"]),  # type: ignore[index]
            foreign_identities=tuple(rag["foreign_identities"]),  # type: ignore[index]
            query_item_ids=tuple(rag["query_item_ids"])),  # type: ignore[index]
        document=None if document is None else DocumentSpec(
            doc_id=str(document["doc_id"]), read_tool=str(document["read_tool"]),  # type: ignore[index]
            format=str(document["format"]),  # type: ignore[index]
            record_count=int(document["record_count"]),  # type: ignore[index]
            record_ids=tuple(document["record_ids"]),  # type: ignore[index]
            extract_to_tool=str(document["extract_to_tool"]),  # type: ignore[index]
            extracted_item_ids=tuple(document["extracted_item_ids"])),  # type: ignore[index]
        has_result=bool(raw["has_result"]),
        streaming=bool(raw["streaming"]),
        revised_from_v4=bool(raw["revised_from_v4"]))


def corpus_digest_v5(cases: Sequence[CaseV5]) -> str:
    """Order- and claim-sensitive, like v4's: the ladder is pinned to it, so a
    corpus that changed by one hop must not be able to reuse yesterday's tiers."""
    digest = hashlib.sha256()
    for case in cases:
        digest.update(json.dumps(case_v5_to_json(case), ensure_ascii=False,
                                 sort_keys=True).encode())
        digest.update(b"\x00")
    return digest.hexdigest()
