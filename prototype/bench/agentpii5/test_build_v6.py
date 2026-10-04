"""The v6 corpus and ladder on disk: the files, the frozen holdout, the miniature.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_build_v6

WHAT THIS PINS THAT NOTHING ELSE DOES. `validate_corpus_v6` sees a LIST of cases;
it cannot see a FILE. Four claims live only here: the v5-shaped file round-trips
to the same digest, the ladder is a MINIATURE of the corpus (K6-13), a truncated
tier is REFUSED rather than renamed silently (R6-37), and the pinned v5 files are
never opened for writing (R6-32). Plus the three printable tables: provenance by
industry (K6-06), the per-tier type counts (K6-20) and the v6 result_pii residue
(K6-17).

EVERYTHING IS WRITTEN INTO A TEMPORARY DIRECTORY. A test that wrote beside the
real `bench/agentpii5/v6/` files would make running the tests a way to change the
corpus.

NOTHING HERE IMPORTS `pseudex`, AND NO CHECK HERE CALLS A MODEL.
"""
import hashlib
import json
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii4 import schema as v4
from bench.agentpii5 import build_v6 as b
from bench.agentpii5.schema import case_v5_from_json, corpus_digest_v5
from bench.agentpii5.test_schema_v6 import (CLEAN_FULL, CLEAN_PILOT, _TOOLS_BY_INDUSTRY,
                                            _REGISTERS, _v6_case)

# The twelve extension industries and their full-corpus counts (TZ §4.4):
# logistics and internal_bi are heavy, the rest light.
_EXTENSION_PLAN: tuple[tuple[str, int], ...] = (
    ("logistics", 60), ("internal_bi", 60), ("insurance", 20), ("auto", 20),
    ("telecom", 20), ("real_estate", 20), ("hospitality", 20), ("hr", 20),
    ("legal", 20), ("government_services", 20), ("education", 20), ("marketing_cdp", 20),
)


def _extension_cases() -> list:
    """The 320 non-pilot cases, ids continuing after the 180 pilot ids, so that
    `CLEAN_PILOT + _extension_cases()` is a grown full corpus with a FROZEN pilot
    block."""
    cases = []
    idx = len(CLEAN_PILOT)
    for industry, count in _EXTENSION_PLAN:
        tool = _TOOLS_BY_INDUSTRY[industry].base.name
        for _ in range(count):
            register = _REGISTERS[idx % len(_REGISTERS)]
            cases.append(_v6_case(idx, industry, register, "single", False, True,
                                  False, False, tool, False))
            idx += 1
    return cases


def _pin_hashes() -> dict[str, str]:
    return {name: hashlib.sha256((b.HERE / name).read_bytes()).hexdigest()
            for name in ("corpus.v5.json", "corpus.json", "ladder.json")}


# --- the build tests ----------------------------------------------------------------

def test_write_corpus_writes_the_v5_shape() -> list[str]:
    """`write_corpus` writes both views, and the v5 view reads back to the same
    digest — a corpus that cannot be read back is a corpus nobody can run."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        digest = b.write_corpus(CLEAN_FULL, out)
        stored = json.loads((out / "corpus.v5.json").read_text(encoding="utf-8"))
        if stored["version"] != 5 or stored["cases"] != len(CLEAN_FULL):
            problems.append(f"corpus.v5.json header is {stored.get('version')}/"
                            f"{stored.get('cases')}, expected 5/{len(CLEAN_FULL)}")
        reread = [case_v5_from_json(row) for row in stored["corpus"]]
        if corpus_digest_v5(reread) != digest:
            problems.append("the written corpus reads back to another digest")
        v4_view = json.loads((out / "corpus.json").read_text(encoding="utf-8"))
        if v4_view["version"] != 4 or v4_view["cases"] != len(CLEAN_FULL):
            problems.append("the v4 view header is wrong")
    return problems


def test_ladder_is_miniature() -> list[str]:
    """K6-13: the written ladder's every tier is a miniature of the pool, and
    covers every industry, type_class and pii_type value from `small` up."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        ladder = b.write_ladder_v6(CLEAN_FULL, Path(folder))
        for line in b.ladder_problems_v6(CLEAN_FULL, ladder):
            problems.append(line)
        for name in ("nano", "small", "medium", "pool", "holdout", "max"):
            if name not in ladder["tiers"]:
                problems.append(f"the ladder has no {name} tier")
    return problems


def test_truncated_tier_refused() -> list[str]:
    """R6-37: a corpus whose pool cannot fill a declared tier is refused, never
    silently truncated under the tier's full name."""
    problems: list[str] = []
    try:
        b.build_ladder_v6(CLEAN_FULL[:50], b.SEED)
        problems.append("a 50-case corpus was given a full ladder without refusal")
    except b.TruncatedTier as error:
        if "R6-37" not in str(error):
            problems.append(f"the refusal does not name R6-37: {error}")
    return problems


def test_pinned_files_untouched() -> list[str]:
    """R6-32: `write_corpus` and `write_ladder_v6` refuse the pinned directory and
    leave the frozen v5 files byte-identical."""
    problems: list[str] = []
    before = _pin_hashes()
    for writer in (b.write_corpus, b.write_ladder_v6):
        try:
            writer(CLEAN_FULL[:5], b.HERE)
            problems.append(f"{writer.__name__} wrote into the pinned directory")
        except b.PinnedPathRefused:
            pass
    after = _pin_hashes()
    if before != after:
        problems.append("the pinned v5 files changed on disk")
    return problems


def test_holdout_frozen() -> list[str]:
    """K6-12: a second build of the same corpus leaves the holdout membership and
    the file untouched."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        first = b.write_ladder_v6(CLEAN_FULL, out)
        bytes_before = (out / "ladder.json").read_bytes()
        again = b.write_ladder_v6(CLEAN_FULL, out)
        if set(first["tiers"]["holdout"]) != set(again["tiers"]["holdout"]):
            problems.append("a second build moved the holdout")
        if (out / "ladder.json").read_bytes() != bytes_before:
            problems.append("a second build changed ladder.json")
    return problems


def test_pilot_holdout_kept() -> list[str]:
    """K6-12's other half: extending the corpus does not move one pilot holdout id
    — the phase-aware draw freezes the pilot block (TZ §4.6)."""
    problems: list[str] = []
    pilot_held = b.draw_holdout_v6(CLEAN_PILOT, b.SEED)
    grown = list(CLEAN_PILOT) + _extension_cases()
    grown_pilot_ids = {case.base.id for case in CLEAN_PILOT}
    grown_pilot_held = {one for one in b.draw_holdout_v6(grown, b.SEED)
                        if one in grown_pilot_ids}
    if grown_pilot_held != pilot_held:
        problems.append(f"the extension moved {len(pilot_held ^ grown_pilot_held)} "
                        f"pilot holdout ids")
    return problems


def test_provenance_table() -> list[str]:
    """K6-06: the provenance share is printed per industry."""
    problems: list[str] = []
    lines = b.provenance_table(CLEAN_FULL)
    industries = {line.split()[0] for line in lines[1:] if line.strip()}
    missing = {industry for industry in ("retail", "medicine", "internal_bi")
               if industry not in industries}
    if missing:
        problems.append(f"the provenance table misses {sorted(missing)}")
    return problems


def test_residue_v6() -> list[str]:
    """K6-17: the v6 result_pii residue prints declared vs crossed."""
    problems: list[str] = []
    lines = b.result_pii_residue_v6(CLEAN_FULL)
    if not any("объявлений" in line for line in lines):
        problems.append(f"the residue table prints no declared/crossed line: {lines[:2]}")
    return problems


def test_tier_type_table() -> list[str]:
    """K6-20: the per-tier number of cases per type is printed."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        ladder = b.write_ladder_v6(CLEAN_FULL, Path(folder))
        lines = b.tier_type_table(CLEAN_FULL, ladder)
    if not any("IMEI" in line for line in lines):
        problems.append("the tier type table names no IMEI column")
    return problems


def test_ladder_survives_the_harness_check() -> list[str]:
    """The ladder's `corpus_sha256` is the digest ITS CONSUMER recomputes.

    `bench.agentpii4.schema.tier` is the gate the harness runs before it plays
    any tier (`harness.main` calls `tier([case.base for case in everything], …)`),
    and it recomputes v4's digest over exactly those bases. `build_ladder_v6`
    stamped `corpus_digest_v5` instead — a digest no consumer of `ladder.json`
    reads — so every v6 dry-run refused with «frozen against corpus 18ed…, this
    corpus is cf1d…», while `corpus.v5.json` read back to its OWN digest: the
    build was proving itself with the wrong witness. This check drives the real
    consumer, and its negative half drives a wrongly-stamped ladder through it.
    """
    problems: list[str] = []
    ladder = b.build_ladder_v6(CLEAN_FULL, b.SEED)
    bases = [case.base for case in CLEAN_FULL]
    mine = v4.Ladder(version=int(ladder["version"]), seed=int(ladder["seed"]),
                     corpus_sha256=str(ladder["corpus_sha256"]),
                     tiers={name: tuple(ids) for name, ids in ladder["tiers"].items()})
    try:
        picked = v4.tier(bases, mine, "nano")
    except v4.InvalidCorpus as refused:
        problems.append(f"the harness's own check refuses the written ladder: {refused}")
        picked = []
    if len(picked) != len(ladder["tiers"]["nano"]):
        problems.append(f"the harness check returned {len(picked)} of "
                        f"{len(ladder['tiers']['nano'])} nano cases")
    # THE NEGATIVE, and it is the frozen check itself: a ladder stamped with the
    # v5 digest (what the writer used to emit) is still refused. Fixing the
    # writer must not have widened `tier`.
    wrong = v4.Ladder(version=mine.version, seed=mine.seed,
                      corpus_sha256=corpus_digest_v5(CLEAN_FULL), tiers=mine.tiers)
    try:
        v4.tier(bases, wrong, "nano")
        problems.append("a ladder stamped with the v5 digest was accepted by tier()")
    except v4.InvalidCorpus:
        pass
    return problems


CHECKS: tuple[Callable[[], list[str]], ...] = (
    test_write_corpus_writes_the_v5_shape,
    test_ladder_survives_the_harness_check,
    test_ladder_is_miniature,
    test_truncated_tier_refused,
    test_pinned_files_untouched,
    test_holdout_frozen,
    test_pilot_holdout_kept,
    test_provenance_table,
    test_residue_v6,
    test_tier_type_table,
)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        for problem in problems:
            print(f"FAIL {check.__name__}: {problem}")
        failures += len(problems)
    print("test_build_v6: PASS" if not failures else f"test_build_v6: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
