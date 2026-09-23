"""ТЗ §2, §3, §8.1 и §8.2 — ПРОТИВ ФАЙЛА, КОТОРЫЙ РЕАЛЬНО ГОНЯЕТСЯ.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_spec_corpus

WHAT THIS PINS THAT NOTHING ELSE DOES, and why a file-level test is not a
duplicate of `test_build.py`. Every existing check of the corpus runs over a
corpus it BUILT in memory (`test_build` calls `build_reporting`, the two
generator suites call their own `PLAN`s, `test_revise` re-revises v4). Nothing
in the tree opens `corpus.v5.json` and asks whether THAT file obeys a single
rule — and `corpus.v5.json` is what `harness.py`, `perfect.py`, `compare.py`
and every published number read. A generator edited without a rebuild leaves
the whole suite green while the instrument runs on yesterday's corpus, and the
digest in `ladder.json` would not catch it either: the ladder is kept, not
redrawn, so a stale pair stays consistent with itself.

AND THE SPEC'S OWN NUMBERS, NOT THE CODE'S. `test_build` reads
`contracts.BEHAVIOUR_FLOORS`, `contracts.MIN_CASES_BY_TYPE`,
`contracts.NEW_TOOL_RETURN_FORMS`; a change to those constants moves the target
and every test stays green. The numbers below are transcribed from
`docs/tz-agentpii5.md` §8.1/§8.2 and kept HERE, so the spec is checked against
the corpus rather than against the code's reading of the spec. Where a ruling
knowingly departs from the spec (R-51's corpus band, R-09/R-16's register mix)
the departure is stated in the check that names it, never smoothed over.

WHAT IS DELIBERATELY NOT A CHECK HERE. §8.2's «доля» column does not hold as a
two-sided band and cannot: the corpus is 1736 cases, so `single` is 34.7 %
against a nominal 15 % while eight families sit below their nominal share, and
K02 is a one-sided floor by ruling. The «≈кейсов» column — the absolute counts
— is what the corpus does meet, and that is what is pinned. The divergence is
reported to the architect, not fixed by a test that asserts what it wishes.

NOTHING HERE IMPORTS `pseudex`, CALLS A MODEL, OR TOUCHES THE NETWORK, and
nothing here rebuilds the corpus file: `build_reporting` is run in MEMORY only,
to compare, because a rebuild on disk would move the digest every published
number is pinned to.
"""
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from bench.agentpii4 import schema as v4
from bench.agentpii5 import build as b
from bench.agentpii5 import contracts as c
from bench.agentpii5 import schema as s
from bench.agentpii5 import tools as v5tools
from bench.agentpii5.contracts import CaseV5

HERE: Path = Path(__file__).resolve().parent
CORPUS_FILE: Path = HERE / "corpus.v5.json"
LADDER_FILE: Path = HERE / "ladder.json"

# --- the spec's own numbers, transcribed from docs/tz-agentpii5.md ------------

# §8.2 «≈кейсов» — the third column of the shares table. Floors, because §8.2
# reads «≥ 900» for the base row and the others are the counts that buy each
# family its MDE; a family may be larger (the revised v4 half supplies `single`
# and `sequential_chain` far past theirs) and none may be smaller.
SPEC_CASE_FLOORS: dict[str, int] = {
    "single": 180, "retry_same_tool": 120, "sequential_chain": 180, "parallel": 100,
    "fanout_pick": 100, "branching": 85, "user_in_loop": 85, "memory_anaphora": 120,
    "rag": 100, "document": 100, "same_tool_other_target": 50,
}
# §8.2 «всего с результатом тула (база) | ≥ 75% | ≥ 900». BOTH halves are
# checked: a share alone would be satisfied by a corpus of 400 cases, and a
# count alone by a corpus of 5 000 in which three quarters reach nothing.
SPEC_WITH_RESULT_SHARE: float = 0.75
SPEC_WITH_RESULT_CASES: int = 900
# §8.2 «цель v5 ≈ 1 200–1 500». R-51 widened the CEILING to 1 800 with its
# reason recorded; the floor is untouched, and this file checks that it stays
# untouched — a ruling that moved the floor would be a different claim.
SPEC_SIZE_BAND: tuple[int, int] = (1200, 1500)
# §8.2 «Типы: INN ≥ 60, PLATE ≥ 60 (сейчас 0)».
SPEC_TYPE_CASE_FLOORS: dict[str, int] = {"INN": 60, "PLATE": 60}
# §8.2 «остальные — не ниже v4»: v4's item counts per type (wiki/BENCHMARK.md §2).
SPEC_V4_ITEM_COUNTS: dict[str, int] = {
    "NAME": 2204, "LOC": 1767, "PHONE": 1275, "DOB": 547, "EMAIL": 472,
    "CARD": 77, "SNILS": 50, "PASSPORT": 50,
}
# §8.2 «кластеры ≥ 3 у ≥ 8 личностей». Two claims in one line, and K08 checks
# only the first: a corpus could hold forty clusters of three that all belong
# to one person, and the bootstrap would resample one identity forty ways.
SPEC_MIN_MULTI_CLUSTERS: int = 8
SPEC_MIN_MULTI_IDENTITIES: int = 8
SPEC_CASES_PER_MULTI: int = 3
# §8.1 + §8.1bis «Итого 55 инструментов, 11 вертикалей» — 44 until 23.09.2026,
# when §8.1bis ordered the OFFICE SUITE's eleven. 43 before that, until the
# clinic's `patient_find` was added: §2 had ordered it from the first revision
# («book, slots, patient_find») and §8.1's table had forgotten it, which left the
# vertical with five WRITING tools and no IN/tool hop at all.
SPEC_TOOL_COUNT: int = 55
SPEC_VERTICAL_COUNT: int = 11
# §8.1's table, «форма возврата» column, verbatim. A tool may declare MORE (R-17:
# a state-decided form is declared as all of them); it may never declare fewer.
SPEC_NEW_TOOL_FORMS: dict[str, tuple[str, ...]] = {
    "kb_search": ("chunks",), "doc_retrieve": ("free_text",),
    "file_read": ("free_text", "list"), "form_parse": ("nested",),
    "bank_client_find": ("single", "list"), "account_statement": ("list",),
    "vehicle_check": ("single", "error_with_value"), "snils_verify": ("single", "empty"),
    "calendar_free": ("list",), "email_send": ("single",),
    "ticket_history": ("free_text",), "courier_status": ("nested",),
    # §8.1bis, the office suite. Read off the SPEC's own table, so an edit to
    # `contracts.NEW_TOOL_RETURN_FORMS` alone cannot move the target.
    "mail_read": ("nested", "free_text", "empty"),
    "mail_search": ("list", "empty", "error_with_value"),
    "mail_send": ("single", "error_with_value"),
    "calendar_invite": ("single", "error_with_value"),
    "reminder_set": ("single", "error_with_value"),
    "tracker_find_user": ("list", "empty"),
    "tracker_issue_create": ("single", "error_with_value"),
    "crm_upsert_card": ("nested", "error_with_value"),
    "memory_save": ("single", "error_with_value"),
    "sheet_append_row": ("list", "error_with_value"),
    "doc_append": ("single", "error_with_value"),
}
# §8.1's table, «ПД в результате» column, for the eight rows that name TYPES
# rather than prose. «суммы», «реквизиты», «шум скана», «всё, что в документе»
# are not v4 item types and are left out rather than guessed at.
SPEC_NEW_TOOL_TYPES: dict[str, tuple[str, ...]] = {
    "kb_search": ("NAME", "PHONE", "LOC"),
    "form_parse": ("NAME", "DOB", "PASSPORT", "SNILS", "LOC"),
    "bank_client_find": ("INN", "CARD", "NAME"),
    "account_statement": ("NAME",),
    "vehicle_check": ("PLATE", "NAME"),
    "snils_verify": ("SNILS", "NAME", "DOB"),
    "calendar_free": ("NAME",),
    "email_send": ("EMAIL",),
    "courier_status": ("NAME", "PHONE", "LOC"),
    # §8.1bis: only the rows whose «ПД в результате» names TYPES. «тело письма»,
    # «сниппет», «документ целиком» are prose, not item types, and are left out
    # rather than guessed at — the same rule the eight rows above follow.
    "mail_send": ("EMAIL",),
    "calendar_invite": ("EMAIL", "NAME"),
    "reminder_set": ("NAME", "PHONE"),
    "tracker_find_user": ("NAME", "EMAIL"),
    "tracker_issue_create": ("NAME",),
    "memory_save": ("NAME",),
}
# §3.6's list of v4 families, which §8.2 says are kept whole. v4 owns the
# canonical tuple; restating twenty-two names here would make a rename of v4's
# corpus look like a v5 defect.
SPEC_V4_KINDS: tuple[str, ...] = v4.SCENARIO_KINDS

# --- the file, read once ------------------------------------------------------

STORED: dict[str, object] = json.loads(CORPUS_FILE.read_text(encoding="utf-8"))
CASES: tuple[CaseV5, ...] = tuple(
    s.case_v5_from_json(row) for row in STORED["corpus"])          # type: ignore[union-attr]
LADDER: dict[str, object] = json.loads(LADDER_FILE.read_text(encoding="utf-8"))


def _counts(values: Sequence[str]) -> dict[str, int]:
    """How many times each label occurs. `collections.Counter` would do; a
    plain dict keeps the return type concrete for the strict-typing rule."""
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return out


def _tool_names(case: CaseV5) -> set[str]:
    """Every tool the case touches — hops, declared returns and the offered
    registry. A vertical reached only through `base.tools` is still reached:
    the model is offered the API and may call it."""
    names = {hop.tool_name for hop in case.hops if hop.tool_name}
    names |= {one.tool_name for one in case.returns}
    names |= set(case.base.tools)
    return names


def _return_forms(case: CaseV5) -> set[str]:
    """The return forms this case exercises. A `ForcedError` IS the
    `error_with_value` form and no `ReturnExpectation` declares it — the mock
    decides the form from the forced ordinal (R-17/R-18) — so counting only
    `returns` would report the form as absent from a corpus that exercises it
    in 126 cases."""
    forms = {one.return_form for one in case.returns}
    if case.forced:
        forms.add("error_with_value")
    return forms


# --- the checks ---------------------------------------------------------------

def test_the_file_is_the_corpus_the_code_builds() -> list[str]:
    """`corpus.v5.json` holds exactly what `build_reporting(SEED, False)` makes.

    WITHOUT THIS, EVERY OTHER SUITE IS ABOUT A CORPUS NOBODY RUNS. `test_build`,
    `test_generator_a`, `test_generator_b` and `test_revise` all build their own
    cases; `harness.py` and `perfect.py` read the file. The two are the same
    corpus only for as long as somebody remembers to rebuild, and the rebuild is
    the one step a hurried change skips.
    """
    problems: list[str] = []
    stored_digest = str(STORED["digest"])
    recomputed = s.corpus_digest_v5(CASES)
    if recomputed != stored_digest:
        problems.append(f"the file's own digest is {stored_digest[:12]}, its cases hash to "
                        f"{recomputed[:12]}")
    built, _downgrades, _dropped = b.build_reporting(b.SEED, False)
    fresh = s.corpus_digest_v5(built)
    if fresh != recomputed:
        stored_ids = [case.base.id for case in CASES]
        fresh_ids = [case.base.id for case in built]
        problems.append(f"the file holds {len(CASES)} cases hashing to {recomputed[:12]}, the "
                        f"build makes {len(built)} hashing to {fresh[:12]} — rebuild it")
        differing = [one for one in fresh_ids if one not in set(stored_ids)]
        if differing:
            problems.append(f"cases the build makes and the file does not: {differing[:5]}")
    return problems


def test_every_case_of_the_file_obeys_the_case_rules() -> list[str]:
    """R01–R21 over the cases ON DISK. The builder raises on a bad case, so a
    freshly built corpus cannot be invalid — which is exactly why a stale or
    hand-edited FILE is the only way an invalid case reaches a run, and the
    only place nothing looked."""
    problems: list[str] = []
    for case in CASES:
        for problem in s.validate_v5(case):
            problems.append(f"{case.base.id}: {problem}")
    return problems[:8]


def test_the_file_obeys_every_corpus_rule() -> list[str]:
    """K01–K15 over the cases ON DISK (K12 lives in the ladder, checked below)."""
    return s.validate_corpus_v5(CASES, tuple(v5tools.REGISTRY_V5))[:8]


def test_the_case_counts_of_the_spec_table() -> list[str]:
    """§8.2's «≈кейсов» column, from the SPEC's numbers rather than from
    `contracts.BEHAVIOUR_FLOORS`.

    THE SHARE COLUMN IS NOT CHECKED HERE, and that is a statement. At 1736 cases
    the nominal percentages cannot all hold — `single` is 34.7 % of a corpus the
    spec sized at 15 % — and K02 is a one-sided floor by ruling. The counts are
    what buy each family its MDE and they are what the corpus meets; the share
    divergence belongs to the architect, not to a check that asserts a wish.
    """
    problems: list[str] = []
    counts = _counts([case.behaviour for case in CASES])
    for behaviour, floor in sorted(SPEC_CASE_FLOORS.items()):
        seen = counts.get(behaviour, 0)
        if seen < floor:
            problems.append(f"§8.2 {behaviour}: {seen} cases, the table asks for {floor}")
    unplanned = sorted(set(counts) - set(SPEC_CASE_FLOORS))
    if unplanned:
        problems.append(f"behaviours the §8.2 table does not name: {unplanned}")
    return problems


def test_the_result_bearing_share_of_the_spec() -> list[str]:
    """§8.2's base row: «всего с результатом тула ≥ 75 % · ≥ 900», both halves."""
    problems: list[str] = []
    with_result = sum(1 for case in CASES if case.has_result)
    share = with_result / len(CASES)
    if share < SPEC_WITH_RESULT_SHARE:
        problems.append(f"§8.2 {share:.1%} of cases reach a tool result, the base row asks "
                        f"for {SPEC_WITH_RESULT_SHARE:.0%}")
    if with_result < SPEC_WITH_RESULT_CASES:
        problems.append(f"§8.2 {with_result} cases reach a tool result, the base row asks "
                        f"for {SPEC_WITH_RESULT_CASES}")
    # The row also names the two hops that make a result a result.
    hollow = [case.base.id for case in CASES if case.has_result
              and not (any(hop.kind == "IN" and hop.owner == "tool" for hop in case.hops)
                       and any(hop.kind == "OUT" and hop.owner == "answer" for hop in case.hops))]
    if hollow:
        problems.append(f"§8.2 «IN-результат + OUT-ответ»: {len(hollow)} cases count as "
                        f"has_result without both hops, e.g. {hollow[:3]}")
    return problems


def test_the_type_floors_of_the_spec() -> list[str]:
    """§8.2 «Типы: INN ≥ 60, PLATE ≥ 60 … остальные — не ниже v4»."""
    problems: list[str] = []
    for kind, floor in sorted(SPEC_TYPE_CASE_FLOORS.items()):
        carrying = sum(1 for case in CASES if any(item.type == kind for item in case.base.pii))
        if carrying < floor:
            problems.append(f"§8.2 type {kind}: {carrying} cases carry it, floor {floor}")
    per_type = _counts([item.type for case in CASES for item in case.base.pii])
    for kind, floor in sorted(SPEC_V4_ITEM_COUNTS.items()):
        seen = per_type.get(kind, 0)
        if seen < floor:
            problems.append(f"§8.2 type {kind}: {seen} items, v4 carried {floor}")
    return problems


def test_the_corpus_size_against_the_spec_band() -> list[str]:
    """§8.2 «цель v5 ≈ 1 200–1 500», and R-51's widening of it.

    THE RULING MOVED ONE END. A corpus of 1736 is outside the spec's band and
    inside the ruling's (1200, 1800) — a knowing departure, recorded with its
    reason. What must not happen quietly is the FLOOR moving: the spec's 1 200
    is what buys ±5pp at the corpus level, and a ruling that lowered it would be
    a different claim about the instrument, not a widening.
    """
    problems: list[str] = []
    total = len(CASES)
    low, high = c.CORPUS_SIZE_BAND_V5
    if low != SPEC_SIZE_BAND[0]:
        problems.append(f"CORPUS_SIZE_BAND_V5 starts at {low}, the spec's floor is "
                        f"{SPEC_SIZE_BAND[0]} — a lowered floor is a new claim, not R-51")
    if high < SPEC_SIZE_BAND[1]:
        problems.append(f"CORPUS_SIZE_BAND_V5 ends at {high}, below the spec's "
                        f"{SPEC_SIZE_BAND[1]}")
    if not low <= total <= high:
        problems.append(f"the corpus holds {total} cases, outside {c.CORPUS_SIZE_BAND_V5}")
    return problems


def test_every_return_form_is_exercised_by_the_corpus() -> list[str]:
    """§2 «у каждого API своя форма возврата — IN-результат меряет подстройку
    под КАЖДУЮ».

    THE REGISTRY DECLARING A FORM IS NOT THE CORPUS EXERCISING IT.
    `test_tools.test_vertical_rules` proves every vertical DECLARES the forms;
    this asks whether a case ever makes one happen, which is the only way an
    IN-result on that form gets measured. `empty` is declared by nine tools and
    exercised by 25 cases — the gap between those two numbers is what this check
    exists for.
    """
    problems: list[str] = []
    seen = _counts([form for case in CASES for form in _return_forms(case)])
    for form in c.RETURN_FORMS:
        count = seen.get(form, 0)
        if count < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"§2 return form {form!r} occurs in {count} cases, below "
                            f"{c.MIN_TYPE_DENOMINATOR} — no denominator to score it on")
    return problems


def test_every_vertical_is_reached_by_the_corpus() -> list[str]:
    """§2's table has eleven verticals and §8.1 keeps them; a vertical no case
    touches is a column of the table the corpus does not measure."""
    problems: list[str] = []
    seen = _counts([c.TOOL_VERTICAL[name] for case in CASES for name in _tool_names(case)
                    if name in c.TOOL_VERTICAL])
    unknown = sorted({name for case in CASES for name in _tool_names(case)}
                     - set(c.TOOL_VERTICAL))
    if unknown:
        problems.append(f"§2 tools filed under no vertical: {unknown[:5]}")
    for vertical in c.VERTICALS:
        count = seen.get(vertical, 0)
        if count < c.MIN_TYPE_DENOMINATOR:
            problems.append(f"§2 vertical {vertical!r} is touched by {count} cases, below "
                            f"{c.MIN_TYPE_DENOMINATOR}")
    return problems


def test_the_voice_axis_carries_a_tool_result() -> list[str]:
    """§3.7 «голос … добавить стриминговые сценарии (SSE), IN-результат в
    голосе».

    R20 says a streaming case is voice; nothing said a streaming case reads
    anything back. A streaming corpus of pure dictation would satisfy every
    existing rule and measure the restoration of an answer that carries no
    tool value — the half of §3.7 that names the IN-result.
    """
    problems: list[str] = []
    streaming = [case for case in CASES if case.streaming]
    if len(streaming) < c.MIN_STREAMING_CASES:
        problems.append(f"§3.7 {len(streaming)} streaming cases, floor {c.MIN_STREAMING_CASES}")
    spoken = set(c.SPEECH_REGISTERS)
    wrong = [case.base.id for case in streaming if case.base.register not in spoken]
    if wrong:
        problems.append(f"§3.7 streaming outside the voice register: {wrong[:3]}")
    silent = [case.base.id for case in streaming
              if not any(hop.kind == "IN" and hop.owner in ("tool", "document")
                         for hop in case.hops)]
    if len(streaming) - len(silent) < c.MIN_STREAMING_CASES:
        problems.append(f"§3.7 {len(streaming) - len(silent)} streaming cases read a tool "
                        f"result, below {c.MIN_STREAMING_CASES}: no IN-result in voice")
    return problems


def test_the_v4_families_survive_with_their_loop() -> list[str]:
    """§3.6 «Уже есть в v4 (сохранить, дополнить хопами 3–4)» and §8.2
    «455 с результатом получают обязательные хопы 3–4».

    ON THE FILE, and per family. `test_revise` re-revises v4 and counts 455;
    this asks whether all twenty-two v4 kinds are still IN the shipped corpus
    and whether each of the 455 carries BOTH added hops — a revision that gave
    a case an IN/tool hop and no answer hop would still be «with a result» by
    `has_result` only because `has_result` demands both, so the check is written
    against the hops themselves rather than against the flag that summarises them.
    """
    problems: list[str] = []
    revised = [case for case in CASES if case.revised_from_v4]
    if len(revised) != c.V4_CORPUS_SIZE:
        problems.append(f"§8.2 {len(revised)} revised cases, v4 has {c.V4_CORPUS_SIZE}")
    kinds = _counts([case.base.kind for case in revised])
    missing = [kind for kind in SPEC_V4_KINDS if kind not in kinds]
    if missing:
        problems.append(f"§3.6 v4 families absent from the shipped corpus: {missing}")
    looped = [case for case in revised
              if any(hop.kind == "IN" and hop.owner == "tool" for hop in case.hops)
              and any(hop.kind == "OUT" and hop.owner == "answer" for hop in case.hops)]
    if len(looped) != c.V4_CASES_WITH_RESULT:
        problems.append(f"§8.2 {len(looped)} revised cases carry hops 3–4, v4 has "
                        f"{c.V4_CASES_WITH_RESULT} with seeds")
    return problems


def test_the_twelve_new_tools_match_the_spec_table() -> list[str]:
    """§8.1's table, read off the SPEC rather than off `contracts`.

    `test_tools.test_examples_resolve` compares the registry with
    `contracts.NEW_TOOL_RETURN_FORMS`; both are code, so an edit to the constant
    takes the test with it. Here the ТЗ's own two columns are the expectation.

    THE TWO COLUMNS ARE CHECKED AGAINST DIFFERENT THINGS, and not by choice. The
    form column is checked against the REGISTRY, where a form is a declared
    `ReturnForm`. The PII column has no registry equivalent: `result_pii` holds
    dotted paths and `spec_v5_for` types only ARGUMENT paths, so for a result
    leaf like `client.inn` nothing in the tree says «this is an INN» except
    `contracts.NEW_TOOL_RESULT_TYPES`. That constant is therefore what the
    table is checked against — the spec against the code's reading of it, which
    is weaker than the form half and is said here rather than implied.
    """
    problems: list[str] = []
    if len(v5tools.REGISTRY_V5) != SPEC_TOOL_COUNT:
        problems.append(f"§8.1 «≈ 43 инструмента»: the registry holds "
                        f"{len(v5tools.REGISTRY_V5)}")
    if len(set(c.TOOL_VERTICAL.values())) != SPEC_VERTICAL_COUNT:
        problems.append(f"§8.1 «11 вертикалей»: the tools fall into "
                        f"{len(set(c.TOOL_VERTICAL.values()))}")
    for name, forms in sorted(SPEC_NEW_TOOL_FORMS.items()):
        spec = v5tools.REGISTRY_V5.get(name)
        if spec is None:
            problems.append(f"§8.1 table names {name!r}, which the registry does not hold")
            continue
        declared = {one.form for one in spec.return_forms}
        missing = sorted(set(forms) - declared)
        if missing:
            problems.append(f"§8.1 {name}: the table asks for {missing}, declared "
                            f"{sorted(declared)}")
    for name, types in sorted(SPEC_NEW_TOOL_TYPES.items()):
        if name not in v5tools.REGISTRY_V5:
            continue
        carried = set(v5tools.result_types(name))
        missing = sorted(set(types) - carried)
        if missing:
            problems.append(f"§8.1 {name}: the table's result carries {missing}, the "
                            f"registry carries {sorted(carried)}")
    return problems


def test_the_holdout_of_the_committed_ladder() -> list[str]:
    """§8.2 «holdout 20% откладывается ДО отладки», on the COMMITTED ladder.

    `test_build.test_holdout_frozen` proves the mechanism in a temporary
    directory; the ladder that decides what a real run reads is this file, and
    nothing opened it. Three ways it can be wrong and none of them is loud: a
    holdout naming cases the corpus no longer has, a holdout that shares ids
    with a debug tier, a holdout that is not a fifth of the corpus.
    """
    problems: list[str] = []
    tiers = LADDER["tiers"]
    if not isinstance(tiers, dict):
        return ["the ladder carries no tiers"]
    ids = {case.base.id for case in CASES}
    holdout = {str(one) for one in tiers.get("holdout", ())}
    stranger = sorted(holdout - ids)
    if stranger:
        problems.append(f"the holdout names {len(stranger)} cases the corpus does not "
                        f"hold, e.g. {stranger[:3]}")
    wanted = round(len(CASES) * c.HOLDOUT_SHARE)
    if abs(len(holdout) - wanted) > 1:
        problems.append(f"the holdout holds {len(holdout)} of {len(CASES)} cases, "
                        f"{c.HOLDOUT_SHARE:.0%} is {wanted}")
    for name, members in sorted(tiers.items()):
        if name in ("holdout", "max"):
            continue
        shared = holdout & {str(one) for one in members}
        if shared:
            problems.append(f"tier {name!r} shares {len(shared)} cases with the holdout, "
                            f"e.g. {sorted(shared)[:3]}")
    return problems


def _ladder() -> v4.Ladder:
    """Файл лестницы как объект. ОДНО чтение на две проверки: два разбора того
    же файла — это два способа назвать ярус, и однажды они разойдутся."""
    tiers = LADDER["tiers"]
    return v4.Ladder(version=int(LADDER.get("version", 2)), seed=int(LADDER.get("seed", 4)),
                     corpus_sha256=str(LADDER.get("corpus_sha256", "")),
                     tiers={str(name): tuple(str(one) for one in ids)
                            for name, ids in dict(tiers).items()})


def test_the_committed_ladder_is_a_miniature_of_the_corpus() -> list[str]:
    """Каждый ярус ФАЙЛА, по которому пойдёт прогон, повторяет корпус по
    регистру, поведению и семье.

    `test_build` доказывает механизм во временном каталоге; решает состав
    прогона ЭТОТ файл, и до 23.09 его не открывал никто: `nano` был 30/30
    voice_raw, `medium` — 300/300, приёмка прибора на каждый push шла на
    `medium`, и четырёх регистров из пяти не видела ни одна проверка. Ярус,
    который перестанет быть миниатюрой (правкой руками, устаревшим штампом,
    выросшим корпусом), обязан покраснеть здесь — там, где лежит файл.
    """
    problems = [f"лестница файла: {line}" for line in b.ladder_problems_v5(CASES, _ladder())]
    # Отрицательная половина: ярус, из которого вынут целый регистр, обязан
    # быть назван — иначе строка выше зеленела бы на любой лестнице.
    ladder = _ladder()
    by_id = {case.base.id: case for case in CASES}
    thinned = [one for one in ladder.tiers["small"]
               if by_id[one].base.register != "chat"]
    broken = replace(ladder, tiers={**ladder.tiers, "small": tuple(thinned)})
    if not any("small" in line and "chat" in line
               for line in b.ladder_problems_v5(CASES, broken)):
        problems.append("ярус без регистра chat принят — проверка не может покраснеть")
    return problems


def test_the_clusters_the_bootstrap_needs() -> list[str]:
    """§8.2 «кластеры ≥ 3 у ≥ 8 личностей (ICC меряется, не предполагается)».

    K08 counts CLUSTERS of size ≥ 3 and stops there. «у ≥ 8 личностей» is the
    other half and nothing asked it: forty clusters of three that all belong to
    one person would pass K08 and give the cluster bootstrap one identity to
    resample forty ways, which is the failure mode clustering exists to prevent.
    """
    problems: list[str] = []
    clusters = _counts([case.base.cluster for case in CASES])
    multi = sum(1 for size in clusters.values() if size >= SPEC_CASES_PER_MULTI)
    if multi < SPEC_MIN_MULTI_CLUSTERS:
        problems.append(f"§8.2 {multi} clusters of ≥ {SPEC_CASES_PER_MULTI} cases, "
                        f"the spec asks for {SPEC_MIN_MULTI_CLUSTERS}")
    identities = _counts([case.base.expects.primary_identity for case in CASES])
    wide = sum(1 for size in identities.values() if size >= SPEC_CASES_PER_MULTI)
    if wide < SPEC_MIN_MULTI_IDENTITIES:
        problems.append(f"§8.2 {wide} identities carry ≥ {SPEC_CASES_PER_MULTI} cases, "
                        f"the spec asks for {SPEC_MIN_MULTI_IDENTITIES}")
    return problems


CHECKS: tuple[Callable[[], list[str]], ...] = (
    test_the_file_is_the_corpus_the_code_builds,
    test_every_case_of_the_file_obeys_the_case_rules,
    test_the_file_obeys_every_corpus_rule,
    test_the_case_counts_of_the_spec_table,
    test_the_result_bearing_share_of_the_spec,
    test_the_type_floors_of_the_spec,
    test_the_corpus_size_against_the_spec_band,
    test_every_return_form_is_exercised_by_the_corpus,
    test_every_vertical_is_reached_by_the_corpus,
    test_the_voice_axis_carries_a_tool_result,
    test_the_v4_families_survive_with_their_loop,
    test_the_twelve_new_tools_match_the_spec_table,
    test_the_holdout_of_the_committed_ladder,
    test_the_committed_ladder_is_a_miniature_of_the_corpus,
    test_the_clusters_the_bootstrap_needs,
)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        if problems:
            failures += 1
            print(f"FAIL {check.__name__}")
            for problem in problems[:6]:
                print(f"  {problem}")
        else:
            print(f"PASS {check.__name__}")
    print(f"test_spec_corpus: {len(CHECKS)} проверок над {len(CASES)} случаями файла · "
          + ("PASS" if not failures else f"FAIL ({failures})"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
