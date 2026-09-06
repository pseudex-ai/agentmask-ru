"""Build the v4 corpus, freeze the ladder, prove the ground truth was built.

    python3 bench/agentpii4/build.py            # write corpus.json + ladder.json
    python3 bench/agentpii4/build.py --check    # validate + prove_no_search, no write

The plan is 360 cases (three per pilot slot): nano 30 / small 120 / medium =
everything. `small` is a stratified subset of the corpus — by kind and by
register — frozen in the ladder and pinned to the corpus digest, so a pilot
re-run is the same measurement and not a re-sample wearing last month's name.
"""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

from bench.agentpii4 import schema, stats, validate
from bench.agentpii4.scenarios import (analytics, chain, compare, container, correction, crm_note,
                                       decompose, derive, long_order, lookup_list, receipt,
                                       result_feed, send_template, summary)
from bench.agentpii4.scenarios import validate as validate_kind
from bench.agentpii4.schema import Case, Ladder

REGISTER_ORDER: tuple[str, ...] = ("voice_raw", "voice_itn", "chat", "sloppy", "clean")

_HERE = Path(__file__).resolve().parent
SEED = 4
# (module, cases in the pilot, cases in the corpus)
PLAN: tuple[tuple[object, int, int], ...] = (
    (chain, 16, 48), (result_feed, 12, 36), (correction, 12, 36),
    (validate_kind, 12, 36), (compare, 14, 42), (summary, 12, 36),
    (container, 10, 30), (derive, 18, 54), (decompose, 14, 42),
    # 05.09: the flow axis (research/2026-09-05-agent-scenario-coverage.md).
    (lookup_list, 10, 30), (crm_note, 8, 24), (send_template, 8, 24), (receipt, 6, 18),
    (analytics, 6, 18),
    # 06.09, Фаза 2 — длинные разговоры с полным набором инструментов.
    (long_order, 8, 60),
)


def build_corpus(seed: int = SEED) -> list[Case]:
    cases: list[Case] = []
    for module, _pilot, total in PLAN:
        cases.extend(module.build(seed, total))  # type: ignore[attr-defined]
    return cases


def _register_round_robin(pool: list[Case], want: int, rng: random.Random) -> list[Case]:
    """`want` cases keeping the register mix, taken round-robin.

    Not `rng.sample`: `clean` is capped at 5% of the corpus, so a proportional
    draw of thirty rounds it to zero and the tier stops covering a register the
    full corpus has. Perlitz's rule for the same problem — cut examples, never
    cut a stratum."""
    by_register: dict[str, list[Case]] = {}
    for case in pool:
        by_register.setdefault(case.register, []).append(case)
    for bucket in by_register.values():
        rng.shuffle(bucket)
    chosen: list[Case] = []
    while len(chosen) < want and any(by_register.values()):
        for register in REGISTER_ORDER:
            if by_register.get(register) and len(chosen) < want:
                chosen.append(by_register[register].pop())
    return chosen


def build_ladder(cases: list[Case], seed: int) -> Ladder:
    """Frozen tiers: proportional by family, register mix kept, strictly nested,
    with a holdout no debug tier may touch.

    THE FAMILIES ARE NOT SAMPLED. There are fourteen of them and they are the
    CLUSTERS; sampling clusters is what makes the design effect bite, while
    taking all of them and sampling WITHIN is stratification, which reduces
    variance instead. Every tier therefore carries every family, with a floor
    of one case each — a tier that has dropped a family cannot answer for it,
    and a per-family verdict from such a tier is a verdict about nothing.
    """
    rng = random.Random(f"v4-ladder:{seed}")
    by_kind: dict[str, list[Case]] = {}
    for case in cases:
        by_kind.setdefault(case.kind, []).append(case)

    # The holdout comes off the top, per family, before any debug tier exists.
    holdout: list[Case] = []
    debug: list[Case] = []
    for kind in sorted(by_kind):
        pool = list(by_kind[kind])
        want = max(1, round(len(pool) * schema.HOLDOUT_SHARE))
        kept = _register_round_robin(pool, want, rng)
        kept_ids = {case.id for case in kept}
        holdout.extend(kept)
        debug.extend(case for case in pool if case.id not in kept_ids)

    debug_by_kind: dict[str, list[Case]] = {}
    for case in debug:
        debug_by_kind.setdefault(case.kind, []).append(case)

    tiers: dict[str, tuple[str, ...]] = {}
    previous: list[Case] = []
    for name in ("nano", "small", "medium", "large"):
        target = min(schema.TIER_SIZES[name], len(debug))
        chosen = list(previous)
        taken = {case.id for case in chosen}
        remaining = target - len(chosen)
        # Proportional to family size, floor one, largest remainder to the
        # biggest families — the allocation rule, not a shuffle.
        quota: dict[str, int] = {}
        for kind in sorted(debug_by_kind):
            already = sum(1 for case in chosen if case.kind == kind)
            share = target * len(debug_by_kind[kind]) / len(debug)
            quota[kind] = max(1, round(share)) - already
        while remaining > 0 and any(value > 0 for value in quota.values()):
            for kind in sorted(quota, key=lambda one: -quota[one]):
                if quota[kind] <= 0 or remaining <= 0:
                    continue
                free = [case for case in debug_by_kind[kind] if case.id not in taken]
                if not free:
                    quota[kind] = 0
                    continue
                pick = _register_round_robin(free, 1, rng)[0]
                chosen.append(pick)
                taken.add(pick.id)
                quota[kind] -= 1
                remaining -= 1
        # Rounding down leaves a tier one or two short of the size it is named
        # for. Topped up from the largest families, which is where the rounding
        # lost them.
        while remaining > 0:
            free_by_kind = {kind: [case for case in pool if case.id not in taken]
                            for kind, pool in debug_by_kind.items()}
            biggest = max(free_by_kind, key=lambda kind: len(free_by_kind[kind]))
            if not free_by_kind[biggest]:
                break
            pick = _register_round_robin(free_by_kind[biggest], 1, rng)[0]
            chosen.append(pick)
            taken.add(pick.id)
            remaining -= 1
        chosen.sort(key=lambda case: case.id)
        tiers[name] = tuple(case.id for case in chosen)
        previous = chosen
    tiers["holdout"] = tuple(sorted(case.id for case in holdout))
    tiers["max"] = tuple(sorted(case.id for case in cases))
    return Ladder(version=2, seed=seed, corpus_sha256=schema.corpus_digest(cases), tiers=tiers)


def ladder_problems(cases: list[Case], ladder: Ladder) -> list[str]:
    """Nesting, coverage and disjointness — checked, never assumed."""
    problems: list[str] = []
    by_id = {case.id: case for case in cases}
    order = ("nano", "small", "medium", "large")
    for smaller, bigger in zip(order, order[1:]):
        missing = set(ladder.tiers[smaller]) - set(ladder.tiers[bigger])
        if missing:
            problems.append(f"ярус {smaller} не вложен в {bigger}: {len(missing)} случаев")
    held = set(ladder.tiers["holdout"])
    for name in order:
        overlap = held & set(ladder.tiers[name])
        if overlap:
            problems.append(f"удержание протекло в {name}: {len(overlap)} случаев")
    if set(ladder.tiers["max"]) != set(by_id):
        problems.append("ярус max не равен корпусу")
    if held | set(ladder.tiers["large"]) != set(by_id) and len(ladder.tiers["large"]) == len(cases) - len(held):
        problems.append("large плюс удержание не покрывают корпус")
    kinds = {case.kind for case in cases}
    for name in (*order, "holdout"):
        covered = {by_id[case_id].kind for case_id in ladder.tiers[name]}
        if covered != kinds:
            problems.append(f"ярус {name} потерял семьи: {sorted(kinds - covered)}")
    return problems


def ladder_table(cases: list[Case], ladder: Ladder) -> list[str]:
    """What each tier can and cannot claim. A size alone says nothing."""
    lines = ["ярусы (K=3; MDE при доле расхождений 0.10 и DEFF 2.1, мощность 80%):"]
    for name in ("nano", "small", "medium", "large", "holdout", "max"):
        size = len(ladder.tiers[name])
        mde = stats.mde_paired(size, 0.10, 2.1)
        lines.append(f"  {name:<8} {size:>4} случаев · {size * 3:>5} плеч · "
                     f"MDE {mde * 100:.1f}pp")
    return lines


def coverage_table(cases: list[Case]) -> list[str]:
    lines = [f"случаев: {len(cases)}"]
    for label, key in (("вид", lambda c: c.kind), ("регистр", lambda c: c.register)):
        counts = Counter(key(case) for case in cases)
        lines.append(f"{label}: " + " · ".join(f"{name} {count}" for name, count in sorted(counts.items())))
    clusters = Counter(case.cluster for case in cases)
    lines.append(f"кластеров: {len(clusters)} · размера ≥3: {sum(1 for n in clusters.values() if n >= 3)}")
    tools = Counter(name for case in cases for name in case.expects.reachable_tools)
    lines.append("инструменты: " + " · ".join(f"{name} {count}" for name, count in sorted(tools.items())))
    distinct, total = validate.find_distinct_share(cases)
    lines.append(f"доказательство: `find` не нашёл бы эталон в {distinct} из {total} случаев")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate and prove, write nothing")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", default=str(_HERE))
    args = parser.parse_args()

    cases, hits = validate.prove_no_search(lambda: build_corpus(args.seed))
    problems = validate.check_all(cases)
    for hit in hits:
        print(f"ПОИСК В ГЕНЕРАТОРЕ: {hit}")
    for problem in problems[:80]:
        print(problem)
    for line in coverage_table(cases):
        print(line)
    if hits or problems:
        print(f"ОТКАЗ: {len(hits)} поисков в генераторе, {len(problems)} проблем", file=sys.stderr)
        return 1
    ladder = build_ladder(cases, args.seed)
    broken = ladder_problems(cases, ladder)
    for line in broken:
        print(f"ЛЕСТНИЦА: {line}")
    for line in ladder_table(cases, ladder):
        print(line)
    if broken:
        print(f"ОТКАЗ: лестница неверна ({len(broken)})", file=sys.stderr)
        return 1
    if args.check:
        # THE CORPUS ON DISK IS WHAT EVERY OTHER SCRIPT READS, and it is not
        # rebuilt by changing the generator. Found on 06.09: the committed
        # `corpus.json` carried digest 617c7b58 while the generator produced
        # 18bea411 — four commits of generator changes that `--check` had
        # validated and `smoke.py` had never seen. A stale corpus does not
        # fail, it MEASURES SOMETHING ELSE, which is worse.
        on_disk = Path(args.out) / "corpus.json"
        if on_disk.exists():
            stored = str(json.loads(on_disk.read_text(encoding="utf-8")).get("digest", ""))
            if stored != ladder.corpus_sha256:
                print(f"ОТКАЗ: на диске корпус {stored[:12]}, генератор даёт "
                      f"{ladder.corpus_sha256[:12]} — пересобери: "
                      f"python3 bench/agentpii4/build.py", file=sys.stderr)
                return 1
        print("корпус собран и проверен, не записан (--check)")
        return 0
    out = Path(args.out)
    (out / "corpus.json").write_text(json.dumps({
        "version": 4, "seed": args.seed, "cases": len(cases),
        "digest": ladder.corpus_sha256,
        "corpus": [case.to_json() for case in cases]}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (out / "ladder.json").write_text(json.dumps({
        "version": ladder.version, "seed": ladder.seed, "corpus_sha256": ladder.corpus_sha256,
        "tiers": {name: list(ids) for name, ids in ladder.tiers.items()}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"записан {out / 'corpus.json'} · digest {ladder.corpus_sha256[:12]} · "
          + " / ".join(f"{name} {len(ids)}" for name, ids in ladder.tiers.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
