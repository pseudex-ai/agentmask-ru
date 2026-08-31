"""AgentPII-RU v3 — corpus assembly and the frozen tier ladder.

Two jobs, and they are separate on purpose. `build_corpus` calls every family
generator and REFUSES to write a file that `schema.require_valid_corpus` rejects;
`build_ladder` cuts the five rungs out of whatever it is handed. A build that
writes an invalid corpus and reports the problems afterwards is the shape v2 had,
and its numbers were published for a month before anybody read the log.

THREE RULES THIS FILE EXISTS TO ENFORCE.

**One stream per family.** Every generator draws from `random.Random(f"v3:{name}:
{seed}")` and nothing else. Five of the six make their own stream from an int
seed; `indirect` takes the generator itself, so it is made here under the same
formula. The alternative — one stream threaded through six generators — makes a
family's output depend on how many draws the families before it happened to make,
so adding one case to `direct` silently redraws all 250 of `toolresult`. That is
not a hypothetical: it is how v2's regenerations kept moving.

**A tier is a stratified frozen set, never a prefix.** v2's ladder was `order[:n]`
of one sequence, so a dimension closed only if that sequence put one of each near
the front — and only `large` did. Here every rung is built in two phases: a greedy
cover that guarantees closure, then a deficit fill that keeps the rung's marginals
near the corpus's. Nesting is by construction, `check_ladder` proves it afterwards
rather than being trusted.

**The pin hashes the CLAIMS, not the ids.** `schema.corpus_digest` walks every
span, every expected call and every link. A re-labelling that keeps the ids —
which is what a corrected offset looks like — moves the digest and the ladder
refuses. An id-only pin stays green while the ground truth walks away underneath
it, and that is the failure a frozen ladder exists to prevent.

**THE PLANNED SIZE IS A CORPUS DECISION, NOT A FAMILY ONE.** Eleven generators
offered 2 001 cases at their own canonical sizes and the agreed band is
1 500-2 000, so six of them are asked for less. Which six, and by how much, is
argued in `AUDIT.md` and summarised in `_TRIM_REASON` below; the short version is
that cases are not the unit a confidence interval is computed over — CLUSTERS
are — so the trim falls hardest on the family with the fewest clusters per case
and the least to say about the two defects this version was built for.

`--allow-incomplete` survives as the escape hatch for a corpus that
`validate_corpus` refuses. It writes NO corpus file; it only lets the ladder and
the audits run against the material that exists, and the ladder it produces
carries `version: 0` so it cannot be mistaken for the frozen one.
"""

import argparse
import hashlib
import json
import random
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

if __package__ in (None, ""):                       # `python3 build.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.agentpii3 import schema
from bench.agentpii3.families import (
    compare, context, direct, indirect, multi, negative, repair, scope,
    spoken_id, toolresult, wordnum)
from bench.agentpii3.schema import Case, InvalidCorpus, Ladder

HERE = Path(__file__).resolve().parent
CORPUS_PATH = HERE / "corpus.json"
LADDER_PATH = HERE / "ladder.json"

# The default run seed. One number, written down, because «the seed we used last
# time» is not a property a benchmark can have.
SEED: int = 20260830

# The generators, in FILE ORDER, which is also vault order: `preceded_by` must
# name a case that comes EARLIER, so this tuple is a scoring-order decision and
# not an alphabetical accident. `scope` goes last because it is the only family
# that uses `preceded_by`, and it points exclusively into cases it emits itself —
# so nothing before it may be re-ordered behind it.
#
# The third column is the PLANNED count, which is what this file asks for, not
# what the module would build unasked. `context` ignores it: its `deep` cases are
# cut from a hand-frozen filler pool and re-cutting would change every long
# case's length. `scope` returns count + 1 — the root case every pair points back
# into is emitted once and belongs to no unit — so 50 there is 51 cases here, and
# the arithmetic below counts what is RETURNED rather than what was asked for.
_Builder = Callable[[int, int], list[Case]]

# Why the six wave-one families are asked for less than they offer. Kept next to
# the numbers because a trim table in a report and a trim applied in code are two
# things that drift, and the report is the one nobody re-runs.
#
# The unit of evidence is the CLUSTER — cases sharing one underlying value —
# because that is what `schema.clusters` bounds a confidence interval over.
# `direct` is 450 cases across 431 clusters, so nearly every case is its own
# observation and cutting it costs almost one observation per case. `indirect` is
# 250 cases across 28 clusters and carries ZERO spoken values, so it contributes
# nothing at all to the two defects v3 exists to measure: the dictated identifier
# and the spoken house number. That asymmetry, and not proportional fairness, is
# where the room for the 631 cases of wave two comes from.
#
# `toolresult` is 200 and not the 178 a proportional cut would give, because it
# REFUSES every count in 158-198 except 168: its own literary share crosses the
# 5% cap in that band and the module raises rather than drifting. A generator
# that can say no is what makes this table checkable instead of arguable.
_TRIM_REASON: dict[str, str] = {
    "direct": "450→396: 431 кластер — больше всего наблюдений на случай в корпусе",
    "compare": "250→200: парные плечи, рез пары стоит обеих половин",
    "indirect": "250→144: 28 кластеров и ни одного произнесённого значения — "
                "самые дешёвые случаи, какие у нас есть",
    "multi": "250→180: многосубъектные случаи плотные, таблицу типов закрывает "
             "и меньшее число",
    "toolresult": "250→200: ОТКАЗЫВАЕТ на 158–198, кроме 168 (его доля "
                  "литературного регистра там переходит 5%)",
    "context": "250, не масштабируется: build() не принимает count, пул deep "
               "заморожен",
}

FAMILY_PLAN: tuple[tuple[str, _Builder, int], ...] = (
    # 396 and not 395: `context` is fixed-size and lost one verbatim case when
    # the partial-annotation screen went in (7 of 168 hand-labelled rows carry
    # something outside their span). The 2 000 is a corpus-level number, so
    # the case comes back from the family that scales, not from the one that
    # cannot.
    ("direct", lambda seed, count: direct.build(seed, count), 396),
    ("compare", lambda seed, count: compare.build(seed, count), 200),
    ("context", lambda seed, count: context.build(seed), 250),
    # `indirect` is handed the generator rather than the seed. Made here, from
    # the same formula the other ten apply to themselves, so the isolation
    # property holds across all eleven and is not ten-elevenths true.
    ("indirect",
     lambda seed, count: indirect.build(
         random.Random(f"v3:indirect:{seed}"), count),
     144),
    ("multi", lambda seed, count: multi.build(seed, count), 180),
    ("toolresult",
     lambda seed, count: toolresult.build(seed, count), 200),
    # Wave two. None of these is trimmed: every one of them exists because a
    # defect class was present in the corpus and not MEASURABLE in it — one
    # instance per type is a class that appears in a table and cannot carry a
    # rate. Cutting them would restore exactly the condition they were built to
    # end.
    ("spoken_id",
     lambda seed, count: spoken_id.build(seed, count), spoken_id.TARGET),
    ("wordnum", lambda seed, count: wordnum.build(seed, count), wordnum.TARGET),
    ("repair", lambda seed, count: repair.build(seed, count), repair.TARGET),
    ("negative",
     lambda seed, count: negative.build(seed, count), negative.TARGET),
    ("scope", lambda seed, count: scope.build(seed, count), scope.TARGET),
)


# --- the corpus -----------------------------------------------------------

def build_corpus_sized(seed: int, counts: dict[str, int]) -> list[Case]:
    """Every family, in file order, each from its own stream.

    `counts` overrides the planned size per module. A generator that cannot hold
    its own composition at the requested size RAISES rather than drifting, which
    is what makes a resize proposal checkable instead of arguable — see the trim
    table in `AUDIT.md`, where `toolresult` refuses whole ranges because its
    literary share would cross the cap.
    """
    unknown = sorted(set(counts) - {name for name, _, _ in FAMILY_PLAN})
    if unknown:
        raise InvalidCorpus(f"no such family module: {unknown}")
    cases: list[Case] = []
    for name, builder, count in FAMILY_PLAN:
        produced = builder(seed, counts.get(name, count))
        if not produced:
            raise InvalidCorpus(f"family module {name!r} produced no cases")
        cases.extend(produced)
    return cases


def build_corpus(seed: int) -> list[Case]:
    """The corpus at its planned size."""
    return build_corpus_sized(seed, {})


def corpus_problems(cases: Sequence[Case]) -> list[str]:
    """Every problem, per case and then corpus-wide. Never the first one only."""
    problems: list[str] = []
    for case in cases:
        problems.extend(schema.validate(case))
    problems.extend(schema.validate_corpus(cases))
    return problems


def write_corpus(cases: Sequence[Case], path: Path, seed: int) -> None:
    """Serialise. Called only after the corpus has been accepted.

    The digest rides IN the file. A corpus and a ladder that disagree about which
    corpus they are is the failure mode a separate checksum file invites, and one
    file with the number inside it cannot be half-copied.
    """
    payload = {
        "version": 3,
        "seed": seed,
        "cases": len(cases),
        "digest": schema.corpus_digest(cases),
        "families": {name: sum(1 for case in cases if case.family == name)
                     for name in schema.FAMILIES},
        "corpus": [case.to_json() for case in cases],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                    encoding="utf-8")


def load_corpus(path: Path) -> list[Case]:
    """Read a corpus file back. Refuses one whose digest has moved."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [schema.case_from_json(raw) for raw in payload["corpus"]]
    actual = schema.corpus_digest(cases)
    if actual != payload["digest"]:
        raise InvalidCorpus(
            f"{path.name} says its digest is {payload['digest'][:12]}, the cases "
            f"in it hash to {actual[:12]}; the file was edited by hand or written "
            f"by a different schema version")
    return cases


# --- the ladder -----------------------------------------------------------
#
# `check_ladder` demands closure on family, register, context, provenance, axis,
# type, duty and spoken. Closure is what phase A buys; phase B buys
# representativeness, and the two are different goals that a single sampler
# cannot serve — a purely proportional draw of thirty cases misses the rare type
# every time, and a pure set cover of thirty is thirty corner cases.

# The dimensions the fill keeps near the corpus's own shape. `selection` is here
# and not in `check_ladder`'s required set on purpose: it is a property of the
# SOURCE and demanding every value of it at nano would spend the rung on
# provenance bookkeeping, but letting a rung drift to all-marker would hide the
# one bias this benchmark was built to avoid.
_SINGLE_DIMENSIONS: tuple[str, ...] = (
    "family", "register", "context", "provenance", "selection")

# Multi-valued per case, so they are averaged rather than summed — a case with
# five types would otherwise outrank five cases with one each, and the fill would
# fill the rung with the corpus's densest cases.
_MULTI_DIMENSIONS: tuple[str, ...] = ("type", "negative")
_MULTI_WEIGHT: float = 0.5


def _facets(case: Case) -> tuple[dict[str, str], dict[str, frozenset[str]]]:
    """The case's coordinates along each balanced dimension."""
    single = {
        "family": case.family,
        "register": case.register,
        "context": case.context,
        "provenance": case.provenance.kind,
        "selection": case.provenance.selection,
    }
    multi = {
        "type": frozenset(item.type for item in case.pii),
        "negative": frozenset(neg.family for neg in case.negatives),
    }
    return single, multi


def _tiebreak(seed: int, case_id: str) -> str:
    """A stable per-case order that depends on the seed and on nothing else.

    Not `rng.shuffle`: a shuffle's result depends on how many draws preceded it,
    which is the same defect the per-family streams exist to avoid, one level up.
    """
    return hashlib.blake2b(f"{seed}:{case_id}".encode("utf-8"),
                           digest_size=8).hexdigest()


def _greedy_cover(cases: Sequence[Case], required: set[tuple[str, str]],
                  seed: int) -> list[str]:
    """The smallest set the greedy rule finds that closes every required pair.

    Greedy, not optimal: minimum set cover is NP-hard and the greedy bound
    (ln|U|) is far inside the budget here — thirty cases against a universe of
    about forty pairs. Optimality would buy a case or two of headroom and cost a
    solver dependency in a file that is supposed to be readable by whoever
    re-scores a competing gateway.
    """
    covers = {case.id: schema.coverage(case) & required for case in cases}
    order = sorted(cases, key=lambda case: _tiebreak(seed, case.id))
    chosen: list[str] = []
    remaining = set(required)
    while remaining:
        best_id = ""
        best_gain = 0
        for case in order:
            if case.id in covers and covers[case.id]:
                gain = len(covers[case.id] & remaining)
                if gain > best_gain:
                    best_gain, best_id = gain, case.id
        if not best_id:
            raise InvalidCorpus(
                f"no case covers the remaining dimensions {sorted(remaining)}; "
                f"the ladder cannot close on a corpus that does not contain them")
        chosen.append(best_id)
        remaining -= covers[best_id]
    return chosen


def _fill(cases: Sequence[Case], chosen: list[str], size: int,
          targets: dict[str, dict[str, float]], seed: int) -> list[str]:
    """Extend `chosen` to `size` by always taking the most under-represented case.

    The score is the DEFICIT: how many cases of each of this candidate's values a
    rung of this size should hold, minus how many it holds. Taking the maximum
    each time is proportional allocation done incrementally, which is what makes
    it nestable — a largest-remainder allocation recomputed per rung is not
    monotone per stratum, so `small` could need a case `nano` did not take, and
    the rungs would stop nesting.
    """
    by_id = {case.id: case for case in cases}
    facets = {case.id: _facets(case) for case in cases}
    current: dict[str, dict[str, float]] = {
        dim: {} for dim in _SINGLE_DIMENSIONS + _MULTI_DIMENSIONS}
    taken = set(chosen)
    for case_id in chosen:
        single, multi = facets[case_id]
        for dim, value in single.items():
            current[dim][value] = current[dim].get(value, 0.0) + 1.0
        for dim, values in multi.items():
            for value in values:
                current[dim][value] = current[dim].get(value, 0.0) + 1.0

    order = sorted(by_id, key=lambda case_id: _tiebreak(seed, case_id))
    while len(taken) < size:
        best_id = ""
        best_score = float("-inf")
        target_size = float(len(taken) + 1)
        for case_id in order:
            if case_id in taken:
                continue
            single, multi = facets[case_id]
            score = 0.0
            for dim, value in single.items():
                score += (targets[dim].get(value, 0.0) * target_size
                          - current[dim].get(value, 0.0))
            for dim, values in multi.items():
                if not values:
                    continue
                score += _MULTI_WEIGHT * sum(
                    targets[dim].get(value, 0.0) * target_size
                    - current[dim].get(value, 0.0)
                    for value in values) / len(values)
            if score > best_score:
                best_score, best_id = score, case_id
        if not best_id:
            raise InvalidCorpus(
                f"the corpus has {len(by_id)} cases, a tier of {size} was asked "
                f"for")
        taken.add(best_id)
        chosen.append(best_id)
        single, multi = facets[best_id]
        for dim, value in single.items():
            current[dim][value] = current[dim].get(value, 0.0) + 1.0
        for dim, values in multi.items():
            for value in values:
                current[dim][value] = current[dim].get(value, 0.0) + 1.0
    return chosen


def build_ladder(cases: Sequence[Case], seed: int, version: int) -> Ladder:
    """The five rungs, nested and stratified, pinned to the corpus's claims."""
    universe: set[tuple[str, str]] = set()
    for case in cases:
        universe |= schema.coverage(case)
    required = {pair for pair in universe
                if pair[0] in ("family", "register", "context", "provenance",
                               "axis", "type", "duty", "spoken")}

    total = float(len(cases))
    targets: dict[str, dict[str, float]] = {
        dim: {} for dim in _SINGLE_DIMENSIONS + _MULTI_DIMENSIONS}
    for case in cases:
        single, multi = _facets(case)
        for dim, value in single.items():
            targets[dim][value] = targets[dim].get(value, 0.0) + 1.0
        for dim, values in multi.items():
            for value in values:
                targets[dim][value] = targets[dim].get(value, 0.0) + 1.0
    for dim in targets:
        for value in targets[dim]:
            targets[dim][value] /= total

    chosen = _greedy_cover(cases, required, seed)
    tiers: dict[str, tuple[str, ...]] = {}
    for name, size in schema.TIER_SIZES.items():
        wanted = size or len(cases)
        if wanted > len(cases):
            raise InvalidCorpus(
                f"tier {name!r} wants {wanted} cases, the corpus has "
                f"{len(cases)}")
        if len(chosen) > wanted:
            raise InvalidCorpus(
                f"tier {name!r} is {wanted} cases but closing every dimension "
                f"already took {len(chosen)}; the rung cannot both close and fit")
        chosen = _fill(cases, chosen, wanted, targets, seed)
        # `max` is the whole corpus, and its order must be FILE order: a vault
        # group is scored in file order and `preceded_by` names a case earlier in
        # it, so a re-ordered `max` would score a scope pair backwards.
        if wanted == len(cases):
            tiers[name] = tuple(case.id for case in cases)
        else:
            tiers[name] = tuple(chosen)
    return Ladder(version=version, seed=seed,
                  corpus_sha256=schema.corpus_digest(cases), tiers=tiers)


def write_ladder(ladder: Ladder, cases: Sequence[Case], path: Path,
                 provisional: str) -> None:
    """Serialise the ladder, with a per-tier claim digest beside the corpus one.

    The per-tier digest is not redundant with `corpus_sha256`. The corpus one
    refuses ANY movement anywhere, which is right and blunt; the tier one says
    WHICH rung's ground truth moved, and that is the difference between «the
    ladder is stale» and «re-check nano, the rest is untouched».
    """
    by_id = {case.id: case for case in cases}
    payload = {
        "version": ladder.version,
        "seed": ladder.seed,
        "corpus_sha256": ladder.corpus_sha256,
        "provisional": provisional,
        "tiers": {name: list(ids) for name, ids in ladder.tiers.items()},
        "tier_sha256": {
            name: schema.corpus_digest([by_id[case_id] for case_id in ids])
            for name, ids in ladder.tiers.items()},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                    encoding="utf-8")


def load_ladder(path: Path) -> Ladder:
    """Read a ladder file. The extra keys are checked, then dropped."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Ladder(version=int(payload["version"]), seed=int(payload["seed"]),
                  corpus_sha256=str(payload["corpus_sha256"]),
                  tiers={name: tuple(ids)
                         for name, ids in payload["tiers"].items()})


# --- reporting ------------------------------------------------------------

def _tally(cases: Sequence[Case], dimension: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        single, multi = _facets(case)
        if dimension in single:
            counts[single[dimension]] = counts.get(single[dimension], 0) + 1
        else:
            for value in multi[dimension]:
                counts[value] = counts.get(value, 0) + 1
    return counts


_REPORT_DIMENSIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("family", schema.FAMILIES),
    ("register", schema.REGISTERS),
    ("context", tuple(schema.CONTEXT_RUNGS)),
    ("provenance", schema.PROVENANCES),
    ("selection", schema.SELECTIONS),
    ("type", schema.TYPES),
)


def coverage_table(cases: Sequence[Case], ladder: Ladder) -> list[str]:
    """The table the owner asked for: every rung against every dimension.

    Counts, not shares, and the corpus column beside them — a share alone cannot
    tell «closed with one case» from «closed with eighty», and at nano that is the
    only distinction that matters.
    """
    by_id = {case.id: case for case in cases}
    names = [name for name in schema.TIER_SIZES if name in ladder.tiers]
    tiers = {name: [by_id[case_id] for case_id in ladder.tiers[name]]
             for name in names}
    lines = [
        f"{'измерение':<14}{'значение':<14}"
        + "".join(f"{name:>8}" for name in names) + f"{'корпус':>9}",
        "-" * (28 + 8 * len(names) + 9),
    ]
    for dimension, vocabulary in _REPORT_DIMENSIONS:
        whole = _tally(cases, dimension)
        per_tier = {name: _tally(rows, dimension) for name, rows in tiers.items()}
        for value in vocabulary:
            if not whole.get(value) and not any(
                    per_tier[name].get(value) for name in names):
                lines.append(f"{dimension:<14}{value:<14}"
                             + "".join(f"{'—':>8}" for _ in names)
                             + f"{'—':>9}   ОТСУТСТВУЕТ В КОРПУСЕ")
                continue
            lines.append(
                f"{dimension:<14}{value:<14}"
                + "".join(f"{per_tier[name].get(value, 0):>8}" for name in names)
                + f"{whole.get(value, 0):>9}")
        lines.append("")
    duties = {name: sum(1 for case in rows for item in case.pii
                        if item.duty == "optional") for name, rows in tiers.items()}
    spoken = {name: sum(1 for case in rows for item in case.pii if item.spoken)
              for name, rows in tiers.items()}
    lines.append(
        f"{'предметов':<14}{'optional':<14}"
        + "".join(f"{duties[name]:>8}" for name in names)
        + f"{sum(1 for c in cases for i in c.pii if i.duty == 'optional'):>9}")
    lines.append(
        f"{'предметов':<14}{'spoken':<14}"
        + "".join(f"{spoken[name]:>8}" for name in names)
        + f"{sum(1 for c in cases for i in c.pii if i.spoken):>9}")
    lines.append(
        f"{'случаев':<28}"
        + "".join(f"{len(tiers[name]):>8}" for name in names)
        + f"{len(cases):>9}")
    lines.append(
        f"{'различных значений':<28}"
        + "".join(f"{sum(schema.distinct_values(tiers[name]).values()):>8}"
                  for name in names)
        + f"{sum(schema.distinct_values(cases).values()):>9}")
    return lines


# --- entry point ----------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", type=Path, default=CORPUS_PATH)
    parser.add_argument("--ladder", type=Path, default=LADDER_PATH)
    parser.add_argument(
        "--allow-incomplete", action="store_true",
        help="build the ladder against a corpus that validate_corpus refuses. "
             "NO corpus file is written, and the ladder is marked provisional.")
    parser.add_argument("--check", action="store_true",
                        help="validate and report; write nothing")
    args = parser.parse_args()

    cases = build_corpus(args.seed)
    problems = corpus_problems(cases)
    digest = schema.corpus_digest(cases)
    print(f"случаев:  {len(cases)}")
    print(f"дайджест: {digest[:16]}")
    print(f"семейства: "
          f"{ {name: sum(1 for c in cases if c.family == name) for name in schema.FAMILIES} }")

    if problems:
        print(f"\nВАЛИДАЦИЯ: {len(problems)} претензий")
        for problem in problems[:20]:
            print(f"  {problem}")
        if len(problems) > 20:
            print(f"  … и ещё {len(problems) - 20}")
        if not args.allow_incomplete:
            print("\nОТКАЗ: корпус не записан. Схема — это спецификация, а не "
                  "совет; корпус, который её не проходит, печатает числа "
                  "неотличимые от верных.")
            return 1
        print("\n--allow-incomplete: корпус НЕ записан, ярус строится "
              "провизорным (version 0).")
    else:
        print("\nвалидация: без замечаний")

    # Determinism is asserted, not assumed. A second build from the same seed
    # must hash the same; if it does not, some family is drawing from a stream
    # this file does not own and the ladder frozen below would pin nothing.
    if schema.corpus_digest(build_corpus(args.seed)) != digest:
        print("ОТКАЗ: два прогона с одним зерном дали разные корпуса")
        return 1

    provisional = ""
    if problems:
        # The reason rides in the file, not only in this terminal. A ladder whose
        # `provisional` field says WHY it is provisional can be read a month
        # later by somebody who did not run the build; `version: 0` alone says
        # only that something was wrong.
        provisional = ("корпус не прошёл валидацию: "
                       + "; ".join(problems[:3])
                       + (f" (и ещё {len(problems) - 3})" if len(problems) > 3
                          else "")
                       + ". Ярус построен на невалидном корпусе и обязан быть "
                         "пересобран с версией 1, когда претензии закрыты.")
    ladder = build_ladder(cases, args.seed, version=0 if problems else 1)
    ladder_problems = schema.check_ladder(cases, ladder)
    if ladder_problems:
        print(f"\nЯРУС: {len(ladder_problems)} претензий")
        for problem in ladder_problems:
            print(f"  {problem}")
        return 1
    print("ярус: вложен, закрывает все измерения")
    print()
    print("\n".join(coverage_table(cases, ladder)))

    if args.check:
        return 0
    if not problems:
        write_corpus(cases, args.out, args.seed)
        print(f"\nзаписан {args.out}")
    write_ladder(ladder, cases, args.ladder, provisional)
    print(f"записан {args.ladder}"
          + (" (провизорный, version 0)" if provisional else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
