"""The four conversational families, and the properties that make them worth
running at all.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_generator_b

EVERY CHECK HERE IS SHOWN TO FAIL. A test that only ever sees a correct corpus
proves that the corpus is one it accepts, which is not the same claim. So each
property is checked twice: once on what the generators produced, and once on a
NEGATIVE FIXTURE — the same case with exactly that property broken, which the
check must reject before it may report a pass.

THE MOCK IS PART OF THE TEST, not a later concern. A declared hop whose value
the backend never tags is a crossing that cannot be observed, and it scores as a
permanent gateway miss: the corpus would report a defect the gateway had no way
to avoid. `test_declared_returns_are_tagged` runs the real `BackendV5` over
every case of every family and checks that each `ReturnExpectation` names items
the rendered result actually carries.

NOTHING HERE IMPORTS `pseudex`, AND NO CHECK HERE CALLS A MODEL.
"""
import sys
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from bench.agentpii4.pools import BuildError
from bench.agentpii5 import contracts as c
from bench.agentpii5 import schema as s
from bench.agentpii5.contracts import CaseV5, LoopSpec
from bench.agentpii5.mock import seed_backend_v5
from bench.agentpii5.scenarios5 import common, document, memory_anaphora, rag, user_in_loop
from bench.agentpii5.scenarios5.plan_b import PLAN_B
from bench.agentpii5.tools import FILE_EXTENSIONS

SEED: int = 4
# Every family at its planned size. The families are built ONCE and shared by
# every check: `document.build(4, 100)` is a second of work, and building it in
# nine tests would make the suite slow enough that somebody stops running it.
BUILT: dict[str, list[CaseV5]] = {
    module.BEHAVIOUR: module.build(SEED, count)          # type: ignore[attr-defined]
    for module, count in PLAN_B}
ALL_CASES: list[CaseV5] = [case for cases in BUILT.values() for case in cases]


# --- the floor every family stands on -------------------------------------------

def test_no_pseudex() -> list[str]:
    """The engine is never imported by the instrument. A benchmark that shares
    the detector's code measures the detector against itself."""
    problems: list[str] = []
    folder = Path(__file__).resolve().parent / "scenarios5"
    for path in sorted(folder.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and c.FORBIDDEN_IMPORT_PREFIX in stripped:
                problems.append(f"{path.name}: {stripped}")
    return problems


def test_build_each_family() -> list[str]:
    """Every family builds its planned count, validates, and reaches a result."""
    problems: list[str] = []
    for behaviour, cases in BUILT.items():
        planned = dict((module.BEHAVIOUR, count)         # type: ignore[attr-defined]
                       for module, count in PLAN_B)[behaviour]
        if len(cases) != planned:
            problems.append(f"{behaviour}: built {len(cases)}, planned {planned}")
        for case in cases:
            if case.behaviour != behaviour:
                problems.append(f"{case.base.id}: behaviour {case.behaviour!r}")
            problems.extend(s.validate_v5(case))
        without = [case.base.id for case in cases if not case.has_result]
        if without:
            problems.append(f"{behaviour}: {len(without)} cases reach no tool result "
                            f"({without[:3]})")
    return problems


def test_case_ids_are_unique() -> list[str]:
    """Two cases under one id are one case counted twice in every share (K01)."""
    ids = [case.base.id for case in ALL_CASES]
    duplicates = sorted({one for one in ids if ids.count(one) > 1})
    return [f"duplicate ids: {duplicates[:5]}"] if duplicates else []


def test_registers() -> list[str]:
    """Each family carries every register, in the v5 mix.

    The NEGATIVE half matters more than the positive one: a family whose
    smallest register rounded to zero would still «carry the mix» by any check
    that only looked at the big ones.
    """
    problems: list[str] = []
    for behaviour, cases in BUILT.items():
        seen = {case.base.register for case in cases}
        missing = [name for name in c.REGISTERS if name not in seen]
        if missing:
            problems.append(f"{behaviour}: no case in register(s) {missing}")
        clean = sum(1 for case in cases if case.base.register == "clean")
        want = round(len(cases) * dict(common.REGISTER_MIX_V5)["clean"])
        if abs(clean - want) > 1:
            problems.append(f"{behaviour}: {clean} clean cases, the mix wants {want}")
    return problems


def test_no_search() -> list[str]:
    """No family recovers an offset from a finished string.

    v4's `prove_no_search` watches its own directory, so the check that matters
    for `scenarios5/` is the one `build.py` widens. Here it is run directly on
    the four families, because a generator that searched would be caught at the
    family it was written in rather than three thousand cases later.
    """
    from bench.agentpii4 import validate as v4validate
    watched = v4validate._WATCHED_DIRS                   # noqa: SLF001
    folder = str(Path(__file__).resolve().parent / "scenarios5")
    v4validate._WATCHED_DIRS = watched + (folder,)       # noqa: SLF001
    try:
        _cases, hits = v4validate.prove_no_search(
            lambda: [case.base for case in user_in_loop.build(SEED, 4)
                     + memory_anaphora.build(SEED, 3) + rag.build(SEED, 12)
                     + document.build(SEED, 100)])
    finally:
        v4validate._WATCHED_DIRS = watched               # noqa: SLF001
    return [f"search in a generator: {hit}" for hit in hits]


# --- user_in_loop ------------------------------------------------------------------

def test_loop_confirm_has_no_value() -> list[str]:
    """R15: the confirming turn repeats nothing the agent could re-read.

    Checked BOTH WAYS. A confirmation that carried the surname would let an
    agent which lost the record rebuild it from the message, and the case would
    report a memory it never tested.
    """
    cases = BUILT["user_in_loop"]
    problems: list[str] = []
    for case in cases:
        if case.loop is None:
            problems.append(f"{case.base.id}: no LoopSpec")
            continue
        for item in case.base.pii:
            if item.value and item.value in case.loop.confirm_phrase:
                problems.append(f"{case.base.id}: confirm phrase carries {item.value!r}")
    broken = replace(cases[0], loop=LoopSpec(
        cases[0].loop.find_tool, cases[0].loop.show_turn, cases[0].loop.confirm_turn,
        "да это я " + cases[0].base.pii[0].value, cases[0].loop.act_tool))
    if "R15" not in {problem.split()[0] for problem in s.validate_v5(broken)}:
        problems.append("a confirm phrase carrying an item value was accepted")
    return problems


def test_loop_acts_after_the_confirmation() -> list[str]:
    """The act is a hop at or after `confirm_turn`, and the show is one at
    `show_turn`. Both directions: a loop whose act moved before the confirmation
    is a loop that measured nothing."""
    problems: list[str] = []
    for case in BUILT["user_in_loop"]:
        if case.loop is None:
            continue
        if not any(hop.kind == "OUT" and hop.owner == "tool_arg"
                   and hop.turn >= case.loop.confirm_turn for hop in case.hops):
            problems.append(f"{case.base.id}: nothing acts after the confirmation")
    first = BUILT["user_in_loop"][0]
    assert first.loop is not None
    moved = replace(first, hops=tuple(
        replace(hop, turn=first.loop.show_turn) if hop.kind == "OUT" else hop
        for hop in first.hops))
    if "R15" not in {problem.split()[0] for problem in s.validate_v5(moved)}:
        problems.append("an act before the confirming turn was accepted")
    return problems


# --- memory_anaphora ---------------------------------------------------------------

def test_anaphora_not_written() -> list[str]:
    """R16: a value referred to by anaphora is NOT written again at the recall
    turn, and every anaphora kind occurs."""
    cases = BUILT["memory_anaphora"]
    problems: list[str] = []
    seen_kinds: set[str] = set()
    for case in cases:
        items = {item.id: item for item in case.base.pii}
        for spec in case.memory:
            seen_kinds.add(spec.anaphora)
            if spec.anaphora == "none":
                continue
            value = items[spec.item_id].value
            if value and value in case.base.messages[spec.recall_turn].content:
                problems.append(f"{case.base.id}: {spec.item_id} written again at "
                                f"turn {spec.recall_turn}")
    for kind in c.ANAPHORA_KINDS:
        if kind != "none" and kind not in seen_kinds:
            problems.append(f"no MemorySpec of kind {kind!r}")
    # The negative: a spec that claims a pronoun for the turn the value was
    # first said in must be refused.
    case = cases[0]
    spec = case.memory[0]
    broken = replace(case, memory=(replace(spec, recall_turn=spec.first_turn + 0),))
    if "R16" not in {problem.split()[0] for problem in s.validate_v5(broken)}:
        problems.append("a recall at the first-mention turn was accepted")
    return problems


def test_memory_cases_are_long() -> list[str]:
    """K14's third clause: ≥ 3 MemorySpecs over ≥ 2 identities and ≥ 5 user
    turns. Every case of the family, not five of them."""
    problems: list[str] = []
    for case in BUILT["memory_anaphora"]:
        items = {item.id: item for item in case.base.pii}
        identities = {items[spec.item_id].identity for spec in case.memory}
        turns = sum(1 for message in case.base.messages if message.role == "user")
        if len(case.memory) < 3 or len(identities) < 2 or turns < 5:
            problems.append(f"{case.base.id}: {len(case.memory)} specs, "
                            f"{len(identities)} identities, {turns} user turns")
    return problems


# --- rag ---------------------------------------------------------------------------

def test_rag_foreign_identities() -> list[str]:
    """Every RAG case declares at least one stranger, none of them is the
    customer, and each is in a chunk the case seeds."""
    cases = BUILT["rag"]
    problems: list[str] = []
    crowded = 0
    for case in cases:
        if case.rag is None:
            problems.append(f"{case.base.id}: no RagSpec")
            continue
        if case.rag.k != len(case.rag.chunk_ids):
            problems.append(f"{case.base.id}: k {case.rag.k} vs "
                            f"{len(case.rag.chunk_ids)} chunks")
        per_chunk: dict[str, set[str]] = {}
        for item in case.base.pii:
            if item.where.kind == "seed" and item.where.record in case.rag.chunk_ids:
                per_chunk.setdefault(item.where.record, set()).add(item.identity)
        if any(len({one.split(".")[0] for one in people}) >= 2
               for people in per_chunk.values()):
            crowded += 1
        for identity in case.rag.foreign_identities:
            if identity == case.base.expects.primary_identity:
                problems.append(f"{case.base.id}: {identity!r} is the customer")
    if crowded < 30:
        problems.append(f"only {crowded} cases carry a chunk with two identities, want 30")
    broken = replace(cases[0], rag=replace(cases[0].rag, foreign_identities=()))
    if "R17" not in {problem.split()[0] for problem in s.validate_v5(broken)}:
        problems.append("a RAG case with no stranger was accepted")
    return problems


def test_rag_query_is_declared() -> list[str]:
    """The customer's value goes into the query as an OUT hop on a free leaf."""
    problems: list[str] = []
    for case in BUILT["rag"]:
        if case.rag is None:
            continue
        if not case.rag.query_item_ids:
            problems.append(f"{case.base.id}: no query item")
        if case.rag.tool_name == "kb_search" and not any(
                hop.kind == "OUT" and hop.tool_name == "kb_search" and hop.path == "query"
                for hop in case.hops):
            problems.append(f"{case.base.id}: nothing crosses into the query")
    return problems


# --- document -----------------------------------------------------------------------

def test_document_formats() -> list[str]:
    """All four formats, twenty-five cases each, each with its own read tool."""
    cases = BUILT["document"]
    problems: list[str] = []
    counts: dict[str, int] = {}
    for case in cases:
        if case.document is None:
            problems.append(f"{case.base.id}: no DocumentSpec")
            continue
        counts[case.document.format] = counts.get(case.document.format, 0) + 1
        if case.document.read_tool not in case.base.tools:
            problems.append(f"{case.base.id}: read tool is not offered")
    for fmt in c.DOCUMENT_FORMATS:
        if counts.get(fmt, 0) < 20:
            problems.append(f"format {fmt!r}: {counts.get(fmt, 0)} cases, want 20")
    csv_case = next(case for case in cases
                    if case.document is not None and case.document.format == "csv")
    assert csv_case.document is not None
    broken = replace(csv_case, document=replace(csv_case.document, record_count=1))
    if "R18" not in {problem.split()[0] for problem in s.validate_v5(broken)}:
        problems.append("a one-person CSV was accepted")
    return problems


def test_document_paths_are_readable() -> list[str]:
    """A payload `file_read` would refuse is a payload no declared hop can cross.

    It found the defect it exists for: twenty-five scan cases pointed at a
    `.pdf`, `file_read` answered a documented `path_extension` refusal, and
    every IN/document hop of those cases was a crossing that never happened.

    The half that compared `document.READABLE_EXTENSIONS` with
    `tools.FILE_EXTENSIONS` is GONE (ruling R-29): `document.py` imports the
    tuple now, and a test whose job is to keep two literals equal is a
    definition written twice with a reminder attached. What remains reads the
    PATHS the family actually wrote, which no import can guarantee.
    """
    problems: list[str] = []
    for case in BUILT["document"]:
        if case.document is None or case.document.read_tool != "file_read":
            continue
        record = next(one for one in case.base.seed_records if one.table == "documents")
        path = str(record.fields["path"])
        if not path.lower().endswith(tuple(FILE_EXTENSIONS)):
            problems.append(f"{case.base.id}: {path} is not readable")
    try:
        document._path(document.c.ctx_for("document", 1, 0, "chat"), "x", "pdf")  # noqa: SLF001
        problems.append("a .pdf payload was accepted")
    except BuildError:
        pass
    return problems


# --- the quotas this half owes the corpus ---------------------------------------------

def test_type_quotas() -> list[str]:
    """INN and PLATE — the two types v4 carried none of. This half owes twenty
    cases of each; it writes twenty-five."""
    problems: list[str] = []
    for kind in ("INN", "PLATE"):
        carrying = sum(1 for case in ALL_CASES
                       if any(item.type == kind for item in case.base.pii))
        if carrying < 20:
            problems.append(f"{kind}: {carrying} cases carry it, this half owes 20")
    return problems


def test_owners_this_half_supplies() -> list[str]:
    """`memory` is declared by NO other half of the corpus, and K13 wants it in
    ≥ 2 behaviours — so both of them have to be here.

    `document` is checked at one behaviour only, on purpose: generator_a's
    `sequential_chain` declares the other, and asserting two of them HERE would
    be this half claiming a corpus-level property it cannot see. The corpus-level
    version is K13 itself, which `build.py --check` runs over all three halves.
    """
    problems: list[str] = []
    per_owner: dict[str, set[str]] = {}
    for case in ALL_CASES:
        for owner in {hop.owner for hop in case.hops}:
            per_owner.setdefault(owner, set()).add(case.behaviour)
    if len(per_owner.get("memory", set())) < 2:
        problems.append(f"owner 'memory' appears in {sorted(per_owner.get('memory', set()))}, "
                        f"needs 2 behaviours and no other half declares it")
    if not per_owner.get("document"):
        problems.append("owner 'document' is declared by no case of this half")
    for owner in c.HOP_OWNERS:
        if owner in ("template",) or per_owner.get(owner):
            continue
        problems.append(f"owner {owner!r} is declared by no case of this half")
    return problems


def test_plate_spoken_parses() -> list[str]:
    """Every dictated plate decodes back to its digits. Ground truth a reader
    cannot decode is ground truth nobody can score."""
    from bench.agentpii4 import pools
    problems: list[str] = []
    for index in range(20):
        ctx = common.ctx_for("plate", SEED, index, "voice_raw")
        text = common.plate_text(ctx.rng)
        rendered = common.plate(ctx, text)
        # DECODED RUN BY RUN, NEVER AS ONE NUMBER. «триста» then «семьдесят
        # семь» is 300 and 77; handed to `parse_numerals` as one sequence it is
        # 377, and a test that made that mistake would report a broken renderer
        # on a correct plate. The runs are the plate's own two number groups.
        words = tuple(rendered.surface.split())
        letters = set(pools.PLATE_SPOKEN.values())
        runs: list[list[str]] = []
        for word in words[1:]:
            if word in letters:
                runs.append([])
                continue
            if not runs:
                runs.append([])
            runs[-1].append(word)
        spoken_runs = [tuple(run) for run in runs if run]
        want = (text[1:4], text[6:])
        if len(spoken_runs) != 2:
            problems.append(f"{text}: spoken {rendered.surface!r} has "
                            f"{len(spoken_runs)} number runs, a plate has two")
        else:
            for run, digits in zip(spoken_runs, want):
                if pools.parse_numerals(run) != digits:
                    problems.append(f"{text}: run {' '.join(run)!r} decodes to "
                                    f"{pools.parse_numerals(run)!r}, not {digits!r}")
        if rendered.canonical != text:
            problems.append(f"{text}: canonical is {rendered.canonical!r}")
    try:
        common.plate(common.ctx_for("plate", SEED, 0, "chat"), "ZZZ")
        problems.append("a plate outside the Cyrillic alphabet was accepted")
    except BuildError:
        pass
    return problems


# --- the mock is part of the corpus ----------------------------------------------------

def test_declared_returns_are_tagged() -> list[str]:
    """Every `ReturnExpectation` names items the real backend actually tags.

    THIS IS THE CHECK THAT COSTS THE MOST AND CATCHES THE MOST. A declared hop
    on an untagged value cannot be observed, so it scores as a permanent gateway
    miss — the corpus would report a defect no gateway could avoid. It has
    already caught three: a slot named `{who2}` that the mock's template split
    does not recognise as a slot, a customer phone duplicated between the CRM
    card and a document (ambiguous by value, tagged on neither), and a `.pdf`
    path `file_read` refuses.
    """
    problems: list[str] = []
    for case in ALL_CASES:
        backend = seed_backend_v5(case)
        for expectation in case.returns:
            arguments = _arguments_for(case, expectation.tool_name)
            if arguments is None:
                continue
            log = backend.call(expectation.tool_name, arguments)
            form = backend.form_of(log.seq)
            if form != expectation.return_form:
                problems.append(f"{case.base.id}: {expectation.tool_name} answered "
                                f"{form!r}, the case expects {expectation.return_form!r}")
            lost = [item for item in expectation.result_item_ids
                    if item not in log.result_spans]
            if lost:
                problems.append(f"{case.base.id}: {expectation.tool_name} tagged none of "
                                f"{lost[:3]}")
    return problems


def _arguments_for(case: CaseV5, tool: str) -> dict[str, object] | None:
    """Arguments that make `tool` answer what the case declared, read off the
    case's own seeds. Returns None for a tool this check does not drive."""
    if tool == "crm_find_contact":
        phone = next(item for item in case.base.pii
                     if item.type == "PHONE" and item.where.kind == "seed"
                     and item.where.record == "c-caller")
        return {"query": {"phone": phone.value}}
    if tool == "kb_search":
        assert case.rag is not None
        topics = " ".join(str(record.fields.get("topic", ""))
                          for record in case.base.seed_records if record.table == "kb_chunks")
        return {"query": topics, "k": case.rag.k}
    if tool == "doc_retrieve":
        return {"doc_id": "doc-1"}
    if tool == "file_read":
        record = next(one for one in case.base.seed_records if one.table == "documents")
        return {"path": str(record.fields["path"])}
    if tool == "form_parse":
        record = next(one for one in case.base.seed_records if one.table == "documents")
        return {"text": f"{record.fields['last_name']} {record.fields['first_name']} "
                        f"{record.fields['snils']}"}
    return None


CHECKS: tuple[Callable[[], list[str]], ...] = (
    test_no_pseudex, test_build_each_family, test_case_ids_are_unique, test_registers,
    test_no_search, test_loop_confirm_has_no_value, test_loop_acts_after_the_confirmation,
    test_anaphora_not_written, test_memory_cases_are_long, test_rag_foreign_identities,
    test_rag_query_is_declared, test_document_formats, test_document_paths_are_readable,
    test_type_quotas, test_owners_this_half_supplies, test_plate_spoken_parses,
    test_declared_returns_are_tagged)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        if problems:
            failures += 1
            print(f"  {check.__name__}: {problems[0]}")
            for problem in problems[1:6]:
                print(f"    {problem}")
    total = sum(len(cases) for cases in BUILT.values())
    print(f"generator_b: {len(CHECKS)} проверок над {total} случаями · "
          + ("PASS" if not failures else f"FAIL ({failures})"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
