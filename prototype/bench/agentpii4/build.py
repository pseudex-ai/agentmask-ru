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

from bench.agentpii4 import schema, validate
from bench.agentpii4.scenarios import (analytics, chain, compare, container, correction, crm_note,
                                       decompose, derive, lookup_list, receipt,
                                       result_feed, send_template, summary)
from bench.agentpii4.scenarios import validate as validate_kind
from bench.agentpii4.schema import Case, Ladder

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
)


def build_corpus(seed: int = SEED) -> list[Case]:
    cases: list[Case] = []
    for module, _pilot, total in PLAN:
        cases.extend(module.build(seed, total))  # type: ignore[attr-defined]
    return cases


def build_ladder(cases: list[Case], seed: int) -> Ladder:
    """Stratified by kind × register; nested (nano ⊂ small ⊂ medium)."""
    rng = random.Random(f"v4-ladder:{seed}")
    by_kind: dict[str, list[Case]] = {}
    for case in cases:
        by_kind.setdefault(case.kind, []).append(case)
    small: list[str] = []
    for module, pilot, _total in PLAN:
        kind = module.__name__.rsplit(".", 1)[-1]  # type: ignore[attr-defined]
        kind = "validate" if kind == "validate" else kind
        pool = list(by_kind[kind])
        rng.shuffle(pool)
        # Keep the register mix: take round-robin over registers.
        by_register: dict[str, list[Case]] = {}
        for case in pool:
            by_register.setdefault(case.register, []).append(case)
        chosen: list[Case] = []
        while len(chosen) < pilot:
            for register in ("voice_raw", "voice_itn", "chat", "sloppy", "clean"):
                if by_register.get(register) and len(chosen) < pilot:
                    chosen.append(by_register[register].pop())
        small.extend(case.id for case in chosen)
    nano = small[::4][:30]
    return Ladder(version=1, seed=seed, corpus_sha256=schema.corpus_digest(cases),
                  tiers={"nano": tuple(nano), "small": tuple(small),
                         "medium": tuple(case.id for case in cases)})


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
    if args.check:
        print("корпус собран и проверен, не записан (--check)")
        return 0
    ladder = build_ladder(cases, args.seed)
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
          f"nano {len(ladder.tiers['nano'])} / small {len(ladder.tiers['small'])} / medium {len(cases)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
