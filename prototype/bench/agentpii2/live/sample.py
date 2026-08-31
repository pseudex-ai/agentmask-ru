"""Which cases the live axis runs, and — printed beside them — which it did not.

WHY THIS SAMPLES WHERE `schema.tier` FREEZES. The offline ladder is a frozen
prefix because its whole value is that last month's nano number and this month's
are about the same twenty cases. The live axis has a different constraint: it
costs money per case, so its rungs are far smaller than the offline ones and a
prefix of the offline ladder at size ten covers three families out of eight. A
frozen prefix that cannot represent five of the eight questions the corpus asks
is not a conservative choice, it is a blind one.

So the draw is STRATIFIED and DETERMINISTIC: the same seed against the same
corpus yields the same ids for ever, and `run.py` writes those ids into the
result file so any run replays exactly with `--ids`. That keeps the comparability
the ladder was protecting without pretending a ten-case prefix is balanced.

ELIGIBILITY IS A PROPERTY OF THE CASE, NOT A CONVENIENCE. The transparency axis
asks whether the model chose the same tool with masking as without. A case
offering no tools cannot answer it in either direction — 79 of the `speech`
family's 96 utterances are bare transcripts with no tool surface at all. They are
excluded and COUNTED, because an excluded population that goes unmentioned is how
a benchmark comes to describe a corpus it never ran.

A case needs no `expected_call` to be eligible. The reference here is the PLAIN
ARM, not the corpus: A/B is what separates «the gateway broke it» from «the model
decided that itself», and it works on any case the model can act on. `calls` is
still read — as a control that says whether the plain arm did the right thing at
all — but a case where the model freelances is still a valid transparency
measurement, and dropping it would quietly restrict the run to the cases the
model finds easy.
"""

import hashlib
import random
from collections import Counter

from bench.agentpii2.schema import DIFFICULTIES, FAMILIES, REGISTERS, Case

# The live rungs. Deliberately NOT `schema.TIER_SIZES`: those are offline sizes
# where a case costs nothing, and reusing the names at different sizes would make
# «nano» mean two things in one repository. These are priced in dollars.
LIVE_TIERS: dict[str, int] = {
    "nano": 10,     # decides nothing; a smoke test with a real bill attached
    "small": 40,    # a family-level signal, no register-level one
    "medium": 120,  # a register-level signal inside the big families
    "large": 320,
    "max": 0,       # every eligible case
}


def eligible(cases: list[Case]) -> list[Case]:
    """Cases the transparency axis can say anything about: the model must have
    something to call. Order is corpus order, which the draw then permutes."""
    return [case for case in cases if case.tools]


def _cell(case: Case) -> tuple[str, str]:
    """The stratum inside a family. Register first because it is the axis the
    corpus was built to vary and the one where the product measurably differs;
    the length rung second, because at these sizes only `length` carries more
    than one of them and stratifying on it elsewhere would draw from an empty
    set and silently fall through to the register order anyway."""
    return (case.register, case.length_rung)


def draw(cases: list[Case], size: int, seed: int) -> list[Case]:
    """A deterministic stratified draw: round-robin over families, and inside a
    family the least-covered (register, rung) cell wins.

    The seed is mixed with the ELIGIBLE ID SET, not with the corpus digest. A
    corpus that grows by a case the live axis cannot run must not silently
    redraw the whole sample — that is the churn `schema.tier` warns about — while
    a corpus whose eligible population really did change SHOULD redraw, because
    the old draw is no longer a stratified sample of it.
    """
    pool = eligible(cases)
    if not pool:
        raise ValueError("ни одного случая с инструментами: живой оси нечего мерить")
    if size <= 0 or size > len(pool):
        size = len(pool)

    fingerprint = hashlib.sha256(
        "\x00".join(sorted(case.id for case in pool)).encode("utf-8")).hexdigest()
    rng = random.Random(f"{seed}:{fingerprint}")

    by_family: dict[str, list[Case]] = {}
    for case in pool:
        by_family.setdefault(case.family, []).append(case)
    for bucket in by_family.values():
        rng.shuffle(bucket)

    # Families in the schema's declared order, restricted to those with an
    # eligible case. Declared order rather than population order so a family that
    # grows does not change which family the first slot goes to.
    families = [name for name in FAMILIES if name in by_family]
    seen: Counter[tuple[str, str]] = Counter()
    taken: list[Case] = []
    taken_ids: set[str] = set()

    while len(taken) < size:
        progressed = False
        for family in families:
            if len(taken) >= size:
                break
            bucket = [case for case in by_family[family] if case.id not in taken_ids]
            if not bucket:
                continue
            # Least-covered cell, ties broken by the seeded shuffle order, which
            # `bucket` preserves — so the choice is total and reproducible.
            best = min(bucket, key=lambda case: seen[_cell(case)])
            taken.append(best)
            taken_ids.add(best.id)
            seen[_cell(best)] += 1
            progressed = True
        if not progressed:
            break
    return taken


def coverage(drawn: list[Case], cases: list[Case]) -> dict[str, list[str]]:
    """What the draw did NOT reach, per axis, plus the ineligible population.

    Printed on every run. A live rung is small enough that most of the corpus is
    always missing, and a report that shows only what ran invites a reader to
    generalise from ten cases to eight families.
    """
    pool = eligible(cases)
    ineligible = [case for case in cases if not case.tools]

    def missing(axis: str, values: tuple[str, ...]) -> list[str]:
        present = {getattr(case, axis) for case in drawn}
        available = {getattr(case, axis) for case in pool}
        return sorted(value for value in values
                      if value in available and value not in present)

    rungs = sorted({case.length_rung for case in pool}
                   - {case.length_rung for case in drawn})
    relations = sorted({case.relation for case in pool}
                       - {case.relation for case in drawn})
    # Counted per family and printed even when the family IS represented by its
    # tool-bearing minority: 79 of `speech`'s 96 utterances are bare transcripts,
    # and a report saying «speech: covered» because seventeen of them offer a
    # tool would describe a family it ran a sixth of.
    excluded = Counter(case.family for case in ineligible)
    return {
        "случаев без инструментов (вне живой оси)": [
            f"{name}: {count}" for name, count in sorted(excluded.items())],
        "семьи не в выборке": missing("family", FAMILIES),
        "регистры не в выборке": missing("register", REGISTERS),
        "сложности не в выборке": missing("difficulty", DIFFICULTIES),
        "длины не в выборке": rungs,
        "отношения не в выборке": relations,
    }
