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
import json
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii4.schema import case_from_json
from bench.agentpii5 import build as b
from bench.agentpii5 import contracts as c
from bench.agentpii5.contracts import CaseV5
from bench.agentpii5.schema import case_v5_from_json, corpus_digest_v5, validate_corpus_v5
from bench.agentpii5.tools import REGISTRY_V5

SEED: int = b.SEED
# Built once. The corpus is 1 594 cases and the whole assembly takes a second;
# doing it in six checks would make the suite slow enough to stop being run.
CASES: list[CaseV5] = b.build_corpus(SEED)


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
        ladder, _lines = b.write_ladder(CASES, SEED, out, True)
        if ladder is None:
            return ["the first build wrote no ladder"]
        first = (out / "ladder.json").read_bytes()
        again, lines = b.write_ladder(CASES, SEED, out, False)
        if again is not None:
            problems.append("a second build rebuilt the ladder without the flag")
        if (out / "ladder.json").read_bytes() != first:
            problems.append("a second build changed ladder.json")
        if not any("--regenerate-ladder" in line for line in lines):
            problems.append("the second build did not say how to redraw the ladder")
        # …and the flag really does redraw it, or the freeze above would be the
        # freeze of a function that never writes.
        shrunk = CASES[: len(CASES) // 2]
        b.write_ladder(shrunk, SEED, out, True)
        if (out / "ladder.json").read_bytes() == first:
            problems.append("--regenerate-ladder on half the corpus changed nothing")
    return problems


def test_holdout_is_disjoint() -> list[str]:
    """The holdout is a fifth of the corpus and appears in no debug tier."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        ladder, _lines = b.write_ladder(CASES, SEED, out, True)
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
    lines = b.coverage_table(CASES) + b.mde_table(CASES) + b.form_disagreements(CASES)
    text = "\n".join(lines)
    for needed in ("поведение:", "регистр (весь корпус):", "регистр (написано в v5):",
                   "с результатом инструмента:", "потоковых:", "владельцы переходов:",
                   "явный conversation_id:", "ожидаемые формы ответа:", "MDE по семьям"):
        if needed not in text:
            problems.append(f"--check prints no {needed!r}")
    for behaviour in c.BEHAVIOURS:
        if not any(line.strip().startswith(behaviour) and "MDE" in line for line in lines):
            problems.append(f"no MDE line for {behaviour!r}")
    for kind in c.MIN_CASES_BY_TYPE:
        if f"{kind}: несут" not in text:
            problems.append(f"no case count for type {kind}")
    return problems


def test_no_search_in_any_generator() -> list[str]:
    """The dynamic proof, widened to `scenarios5/`. v4's own watch list does not
    include it, so an unwidened run would prove the property of the half that no
    longer needs proving."""
    _cases, hits = b.prove_no_search_v5(SEED)
    return [f"search in a generator: {hit}" for hit in hits]


def test_widened_watch_is_restored() -> list[str]:
    """The watch list is put back. A module-level tuple left extended would make
    every later v4 run watch a directory v4 does not own."""
    from bench.agentpii4 import validate as v4validate
    before = v4validate._WATCHED_DIRS                    # noqa: SLF001
    b.prove_no_search_v5(SEED)
    after = v4validate._WATCHED_DIRS                     # noqa: SLF001
    return [] if before == after else [f"watch list left as {after}"]


CHECKS: tuple[Callable[[], list[str]], ...] = (
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
