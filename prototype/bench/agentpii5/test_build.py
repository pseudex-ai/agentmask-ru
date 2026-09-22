"""The assembled corpus, its two files, and the holdout that must not move.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_build

WHAT THIS PINS THAT NOTHING ELSE DOES. `validate_v5` answers for a case and
`validate_corpus_v5` for a list of cases; neither can see a FILE. Three claims
live only here: the v4 view on disk is readable by v4's own reader, the v5 file
round-trips to the same digest, and the holdout tier is frozen — a second build
without `--regenerate-ladder` leaves `ladder.json` byte for byte as it was.

THE HOLDOUT IS THE ONE THAT MATTERS (K12). Its whole value is that it was drawn
before anyone looked; a build that redrew it whenever the corpus grew would hand
back twenty per cent of the corpus that had seen every debugging run of the
week, and no number computed on it would mean what it says.

EVERYTHING IS WRITTEN INTO A TEMPORARY DIRECTORY. A test that wrote
`corpus.v5.json` beside the real one would make running the tests a way to
change the corpus.

NOTHING HERE IMPORTS `pseudex`, AND NO CHECK HERE CALLS A MODEL.
"""
import ast
import json
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from bench.agentpii4.schema import case_from_json
from bench.agentpii5 import build as b
from bench.agentpii5 import contracts as c
from bench.agentpii5 import revise as revise_module
from bench.agentpii5.contracts import CaseV5
from bench.agentpii5.schema import case_v5_from_json, corpus_digest_v5, validate_corpus_v5
from bench.agentpii5.tools import REGISTRY_V5

SEED: int = b.SEED
# Built once, THROUGH THE REPORTING PATH. The corpus is 1 736 cases and the whole
# assembly takes a second; doing it in six checks would make the suite slow
# enough to stop being run. `build_reporting` is the same build plus the
# downgrades counted by reason — what `chain_table` prints — so taking it here
# costs nothing and lets the printed table be checked against the real counter
# rather than against one made up for the test.
CASES, DOWNGRADES, _DROPPED = b.build_reporting(SEED, False)


def test_corpus_size_and_plan() -> list[str]:
    """Every planned family contributes its count, and the total is the three
    halves added up — not a number that happens to be in the band."""
    problems: list[str] = []
    revised = sum(1 for case in CASES if case.revised_from_v4)
    planned = sum(count for _module, count in b.PLAN)
    if revised != c.V4_CORPUS_SIZE:
        problems.append(f"{revised} revised cases, v4 has {c.V4_CORPUS_SIZE}")
    if len(CASES) != revised + planned:
        problems.append(f"{len(CASES)} cases, expected {revised} + {planned}")
    low, high = c.CORPUS_SIZE_BAND_V5
    if not low <= len(CASES) <= high:
        problems.append(f"{len(CASES)} cases, band {c.CORPUS_SIZE_BAND_V5}")
    return problems


def test_corpus_rules() -> list[str]:
    """Every corpus rule, reported in full rather than as a count. K03 is
    enforced here with the other fourteen: it was red at 73.1 % until ruling
    R-23 converted the authored no-result cases (1203 / 1594 = 75.5 %), and the
    tripwire that printed that arithmetic retired the day it went green."""
    return validate_corpus_v5(CASES, tuple(REGISTRY_V5))


def test_v4_view_loads() -> list[str]:
    """v4's own reader opens every entry of the v4 view, and the digest in the
    file is the one v4 computes over it."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        b.write_corpus(CASES, out)
        stored = json.loads((out / "corpus.json").read_text(encoding="utf-8"))
        if len(stored["corpus"]) != len(CASES):
            problems.append(f"the v4 view holds {len(stored['corpus'])} of {len(CASES)}")
        for row in stored["corpus"]:
            case_from_json(row)
        identifiers = [row["id"] for row in stored["corpus"]]
        if identifiers != [case.base.id for case in CASES]:
            problems.append("the v4 view is not in corpus order")
    return problems


def test_v5_round_trip() -> list[str]:
    """The v5 file reads back to the same digest — and a doctored file does not.

    A corpus that cannot be read back is a corpus nobody can run, and the digest
    is what the ladder is pinned to, so «reads back» has to mean «reads back
    identically» rather than «parses».
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        digest = b.write_corpus(CASES, out)
        stored = json.loads((out / "corpus.v5.json").read_text(encoding="utf-8"))
        reread = [case_v5_from_json(row) for row in stored["corpus"]]
        if corpus_digest_v5(reread) != digest:
            problems.append("the written corpus reads back to another digest")
        if stored["digest"] != digest:
            problems.append("the file's own digest is not the corpus's")
        doctored = list(stored["corpus"])
        doctored[0] = dict(doctored[0])
        doctored[0]["streaming"] = not doctored[0]["streaming"]
        if corpus_digest_v5([case_v5_from_json(row) for row in doctored]) == digest:
            problems.append("flipping one case's streaming flag left the digest equal")
    return problems


def test_holdout_frozen() -> list[str]:
    """K12: a second build without the flag leaves `ladder.json` byte-identical,
    and `--regenerate-ladder` is the only thing that may touch it."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        ladder, _lines, broken = b.write_ladder(CASES, SEED, out, True, False)
        if ladder is None or broken:
            return [f"the first build wrote no ladder: {broken}"]
        first = (out / "ladder.json").read_bytes()
        again, lines, broken = b.write_ladder(CASES, SEED, out, False, False)
        if again is not None:
            problems.append("a second build rebuilt the ladder without the flag")
        if broken:
            problems.append(f"an unchanged corpus was refused its own ladder: {broken}")
        if (out / "ladder.json").read_bytes() != first:
            problems.append("a second build changed ladder.json")
        if not any("--regenerate-ladder" in line for line in lines):
            problems.append("the second build did not say how to redraw the ladder")
        # …and the flag is not a way PAST the freeze either: a corpus that lost
        # half its cases would redraw the holdout of the survivors, so the
        # regeneration is refused and the file stays exactly as it was. The
        # freeze above would otherwise be the freeze of a function that never
        # writes, and this is the write it declines to make.
        shrunk = CASES[: len(CASES) // 2]
        _ladder, _lines, broken = b.write_ladder(shrunk, SEED, out, True, False)
        if not broken:
            problems.append("--regenerate-ladder on half the corpus moved the holdout "
                            "without saying so")
        if (out / "ladder.json").read_bytes() != first:
            problems.append("a refused regeneration wrote the file anyway")
    return problems


def test_a_changed_corpus_refuses_the_kept_ladder() -> list[str]:
    """THE DIRECTION K12 IS ACTUALLY ABOUT, and the one nothing watched.

    The freeze above only ever saw a corpus that had not changed. Rebuilding
    with another seed into a directory holding today's ladder printed «лестница
    оставлена как есть» and exited 0 while 162 of 319 holdout ids named a
    DIFFERENT case — a holdout frozen against nothing. The refusal names both
    digests, and `--regenerate-ladder` is refused in turn if it would move a
    case that still exists between tiers.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        b.write_ladder(CASES, SEED, out, True, False)
        mutated = [replace(CASES[0], base=replace(CASES[0].base, now="2031-01-01T00:00:00+03:00"))]
        mutated.extend(CASES[1:])
        kept, _lines, broken = b.write_ladder(mutated, SEED, out, False, False)
        if kept is not None:
            problems.append("a changed corpus rebuilt the ladder by itself")
        if not broken:
            problems.append("a corpus with another digest kept the ladder silently")
        elif "--regenerate-ladder" not in broken[0]:
            problems.append(f"the refusal does not name the way out: {broken[0]}")
        # …and the refusal is about the DIGEST, not about any change: the same
        # cases are accepted again.
        _kept, _lines, still = b.write_ladder(CASES, SEED, out, False, False)
        if still:
            problems.append(f"the unchanged corpus was refused too: {still}")
    return problems


def test_regeneration_keeps_the_holdout() -> list[str]:
    """`--regenerate-ladder` may distribute NEW cases and may not move an
    existing one: a holdout that changed tier is a holdout that has seen the
    debugging it was drawn to avoid."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        b.write_ladder(CASES, SEED, out, True, False)
        first = json.loads((out / "ladder.json").read_text(encoding="utf-8"))
        _ladder, _lines, broken = b.write_ladder(CASES, SEED, out, True, False)
        if broken:
            problems.append(f"an identical corpus moved its own holdout: {broken}")
        # The negative: a ladder whose holdout was drawn from ANOTHER corpus must
        # be refused, and `_holdout_moved` is what says so.
        foreign = dict(first)
        tiers = {name: list(ids) for name, ids in first["tiers"].items()}
        tiers["holdout"] = [identifier for identifier in tiers["holdout"]][:-1]
        moved_out = first["tiers"]["holdout"][-1]
        foreign["tiers"] = tiers
        (out / "ladder.json").write_text(json.dumps(foreign, ensure_ascii=False),
                                         encoding="utf-8")
        _ladder, _lines, broken = b.write_ladder(CASES, SEED, out, True, False)
        if not broken:
            problems.append(f"a holdout missing {moved_out} was accepted as frozen")
        # …AND THE ONE TIME IT MAY MOVE (R-52). The assertion that no live run
        # has read this ladder yet is the only thing that lets the same movement
        # through, and it has to SAY how many cases changed tier — a redraw that
        # moved a fifth of the corpus quietly is the failure the refusal above
        # exists for.
        _ladder, lines, broken = b.write_ladder(CASES, SEED, out, True, True)
        if broken:
            problems.append(f"the assertion did not let the one allowed redraw through: "
                            f"{broken}")
        if not any("сменили ярус" in line for line in lines):
            problems.append("the allowed redraw did not report the movement it made")
    return problems


def test_holdout_is_disjoint() -> list[str]:
    """The holdout is a fifth of the corpus and appears in no debug tier."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        ladder, _lines, _broken = b.write_ladder(CASES, SEED, out, True, False)
        if ladder is None:
            return ["no ladder was written"]
        held = set(ladder.tiers["holdout"])
        for name in ("nano", "small", "medium", "large"):
            overlap = held & set(ladder.tiers[name])
            if overlap:
                problems.append(f"{len(overlap)} holdout cases leaked into {name}")
        share = len(held) / len(CASES)
        if abs(share - c.HOLDOUT_SHARE) > 0.03:
            problems.append(f"holdout is {share:.1%} of the corpus, want "
                            f"{c.HOLDOUT_SHARE:.0%}")
        if set(ladder.tiers["max"]) != {case.base.id for case in CASES}:
            problems.append("the max tier is not the corpus")
    return problems


def test_check_prints_shares() -> list[str]:
    """The tables a reader needs are actually printed: behaviours, both register
    views, the result share, the two new types, the owners, and an MDE line per
    family."""
    problems: list[str] = []
    lines = (b.coverage_table(CASES) + b.mde_table(CASES) + b.form_disagreements(CASES)
             + b.loop_table(CASES) + b.chain_table(CASES, DOWNGRADES)
             + b.downgrade_lines(DOWNGRADES))
    text = "\n".join(lines)
    for needed in ("поведение:", "регистр (весь корпус):", "регистр (написано в v5):",
                   "с результатом инструмента:", "потоковых:", "владельцы переходов:",
                   "явный conversation_id:", "формы ответа (проверены на реальном моке):",
                   "одиночные:", "цепочки:", "написано в v5", "ушло по R-49",
                   "MDE по семьям"):
        if needed not in text:
            problems.append(f"--check prints no {needed!r}")
    for behaviour in c.BEHAVIOURS:
        if not any(line.strip().startswith(behaviour) and "MDE" in line for line in lines):
            problems.append(f"no MDE line for {behaviour!r}")
    for kind in c.MIN_CASES_BY_TYPE:
        if f"{kind}: несут" not in text:
            problems.append(f"no case count for type {kind}")
    return problems


def test_the_authored_and_the_revised_halves_are_counted_apart() -> list[str]:
    """R-50 and R-49 in the printed tables: `single` and `sequential_chain` are
    each a family the revised corpus supplies part of, and one number for either
    would be read as a claim about a shape most of it does not have.

    THE NUMBERS ARE CHECKED AGAINST THE CORPUS, not against a literal. A table
    that printed «написано в v5 100» while the plan built ninety would be a table
    nobody could use, and a literal here would have to be edited every time the
    plan does.
    """
    problems: list[str] = []
    text = "\n".join(b.loop_table(CASES) + b.chain_table(CASES, DOWNGRADES))
    for behaviour in ("single", "sequential_chain"):
        authored = sum(1 for case in CASES
                       if case.behaviour == behaviour and not case.revised_from_v4)
        revised = sum(1 for case in CASES
                      if case.behaviour == behaviour and case.revised_from_v4)
        if f"написано в v5 {authored}" not in text:
            problems.append(f"{behaviour}: the table does not print «написано в v5 "
                            f"{authored}»")
        if f"ревизия v4 {revised}" not in text:
            problems.append(f"{behaviour}: the table does not print «ревизия v4 {revised}»")
    left = sum(count for label, count in DOWNGRADES.items()
               if label.endswith(revise_module.MUTATING_REASON))
    if not left:
        problems.append("no case left sequential_chain under R-49; either the rule is gone "
                        "or the v4 corpus stopped carrying an update fed by a lookup")
    if f"ушло по R-49 (аргумент мутирующего вызова — сказанное клиентом) {left}" not in text:
        problems.append(f"the chain table does not print the R-49 departures ({left})")
    # THE NEGATIVE: with no downgrades reported the line must not claim any.
    if "клиентом) 0" not in "\n".join(b.chain_table(CASES, Counter())):
        problems.append("an empty downgrade counter still printed R-49 departures")
    return problems


def test_regenerating_the_ladder_needs_the_assertion() -> list[str]:
    """R-52: the holdout may be redrawn only while nobody has run against it, and
    the caller has to SAY so — `--regenerate-ladder` is what to do, not what is
    true.

    BOTH ANSWERS, because a refusal that has only ever been watched refusing
    could be a function that returns a string unconditionally.
    """
    problems: list[str] = []
    refusal = b.ladder_refusal(True, False)
    if "--unfrozen-before-first-run" not in refusal:
        problems.append(f"redrawing without the assertion was not refused by name: "
                        f"{refusal!r}")
    if b.ladder_refusal(True, True):
        problems.append("the assertion did not let the redraw through")
    if b.ladder_refusal(False, False):
        problems.append("an ordinary build was refused a ladder it does not redraw")
    return problems


def test_no_search_in_any_generator() -> list[str]:
    """The dynamic proof, widened to `scenarios5/`. v4's own watch list does not
    include it, so an unwidened run would prove the property of the half that no
    longer needs proving."""
    _cases, hits = b.prove_no_search_v5(SEED)
    return [f"search in a generator: {hit}" for hit in hits]


def test_static_proof_sees_containment() -> list[str]:
    """The `in` operator and a hand-rolled scan, which the dynamic watch cannot
    see at all.

    THE REPRODUCTION THIS PINS (corpus-lens/proof_nosearch.py): `str.find`
    inside a watched directory was caught, `x in y` and a slice scan were not,
    and `revise.py` — which builds 834 of the 1 594 cases and did ask
    `item.value in case.messages[turn].content` — was outside the watched set
    entirely.
    """
    problems: list[str] = []
    if b.static_search_hits():
        problems.append(f"a builder searches a finished string: {b.static_search_hits()[0]}")
    watched = {Path(one).name for one in b.WATCHED_V5}
    for needed in ("revise.py", "build.py", "scenarios5"):
        if needed not in watched:
            problems.append(f"{needed} is not watched")
    # THE NEGATIVE: each forbidden shape, read off its own AST.
    for source, why in (("item.value in case.messages[turn].content", "the `in` operator"),
                        ("case.messages[t].content.find(value)", "str.find"),
                        ("log.result_text.startswith(value)", "startswith"),
                        ("re.search(pattern, rendered)", "re.search"),
                        ("body.index(value)", "str.index")):
        node = ast.parse(source, mode="eval").body
        if not any(b._searched_surface(one) for one in ast.walk(node)):   # noqa: SLF001
            problems.append(f"the static proof does not see {why}")
    # …and it does not fire on what a builder legitimately does.
    for source in ("writer.put(text, tag)", "x in values", "text.replace(old, new)"):
        node = ast.parse(source, mode="eval").body
        if any(b._searched_surface(one) for one in ast.walk(node)):       # noqa: SLF001
            problems.append(f"the static proof fires on {source!r}")
    return problems


def test_every_case_proves_its_declaration() -> list[str]:
    """`build` refuses a corpus whose declarations the real backend does not
    produce (T1, T4, T5): a phantom result item, a return form the tool does not
    answer in, an IN hop with no rendered span."""
    problems: list[str] = []
    if b.proof_problems(CASES):
        problems.append(f"the built corpus does not prove itself: "
                        f"{b.proof_problems(CASES)[0]}")
    with_return = next(case for case in CASES if case.returns)
    phantom = replace(with_return, returns=(replace(
        with_return.returns[0],
        result_item_ids=with_return.returns[0].result_item_ids + ("ghost",)),))
    if not b.proof_problems([phantom]):
        problems.append("a declared result item the backend never renders passed the build")
    forms = {one.form for one in REGISTRY_V5[with_return.returns[0].tool_name].return_forms}
    other = sorted(forms - {with_return.returns[0].return_form})
    if not other:
        problems.append(f"{with_return.returns[0].tool_name} declares one form only; "
                        f"pick another case for the form negative")
    elif not b.proof_problems([replace(with_return, returns=(
            replace(with_return.returns[0], return_form=other[0]),))]):
        problems.append("a wrong return_form passed the build")
    return problems


def test_widened_watch_is_restored() -> list[str]:
    """The watch list is put back. A module-level tuple left extended would make
    every later v4 run watch a directory v4 does not own."""
    from bench.agentpii4 import validate as v4validate
    before = v4validate._WATCHED_DIRS                    # noqa: SLF001
    b.prove_no_search_v5(SEED)
    after = v4validate._WATCHED_DIRS                     # noqa: SLF001
    return [] if before == after else [f"watch list left as {after}"]


CHECKS: tuple[Callable[[], list[str]], ...] = (
    test_the_authored_and_the_revised_halves_are_counted_apart,
    test_regenerating_the_ladder_needs_the_assertion,
    test_a_changed_corpus_refuses_the_kept_ladder, test_regeneration_keeps_the_holdout,
    test_static_proof_sees_containment, test_every_case_proves_its_declaration,
    test_corpus_size_and_plan, test_corpus_rules,
    test_v4_view_loads, test_v5_round_trip, test_holdout_frozen, test_holdout_is_disjoint,
    test_check_prints_shares, test_no_search_in_any_generator,
    test_widened_watch_is_restored)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        if problems:
            failures += 1
            print(f"  {check.__name__}: {problems[0]}")
            for problem in problems[1:5]:
                print(f"    {problem}")
    print(f"build: {len(CHECKS)} проверок над {len(CASES)} случаями · "
          + ("PASS" if not failures else f"FAIL ({failures})"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
