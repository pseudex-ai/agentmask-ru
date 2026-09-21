"""Generate the corpus: one JSON file per case under `cases/<family>/`.

    python3 -m agentmask_ru.build --seed 20260920 --out cases/
    python3 -m agentmask_ru.build --seed 20260920 --out cases/ --check

`--check` regenerates into a temporary directory and compares, so CI can
prove the committed corpus is exactly what this seed produces (gate G9). A
corpus nobody can regenerate is a corpus nobody can audit.

THE PLAN IS FIXED, NOT SAMPLED. Families, registers and name tiers are
allocated by an explicit table below rather than drawn at random, so every
stratum the report prints has a known size and a seed change cannot quietly
empty one. Only the VALUES are random.
"""

import argparse
import datetime as dt
import filecmp
import random
import shutil
import sys
import tempfile
from pathlib import Path

from agentmask_ru.families import BUILDERS, content_digest
from agentmask_ru.pools import load_pools
from agentmask_ru.schema import Case, dump, load_dir, validate

# How many cases of each family, and in which registers. `check_status` and
# `refund` carry no name, so they need no tier spread and get fewer cases.
PLAN: dict[str, dict[str, int]] = {
    "create_order":    {"clean": 18, "chat": 22, "sloppy": 20},
    "verify_identity": {"clean": 16, "chat": 18, "sloppy": 16},
    "second_mention":  {"clean": 16, "chat": 20, "sloppy": 16},
    "send_sms":        {"clean": 12, "chat": 16, "sloppy": 12},
    "check_status":    {"clean": 12, "chat": 14, "sloppy": 12},
    "refund":          {"clean": 10, "chat": 12, "sloppy": 10},
    # Added in v0.2: the tool wants the PARTS. Appended, so the streams of the
    # six families above are untouched and their cases stay byte-identical.
    "decompose":       {"clean": 14, "chat": 16, "sloppy": 12},
}

# The tier mix for families that carry a name. «common» is what every
# gazetteer holds; the other three are where a benchmark can still fail.
TIER_MIX: tuple[tuple[str, int], ...] = (("common", 40), ("tail", 30), ("diminutive", 15), ("foreign", 15))

NAMED_FAMILIES: frozenset[str] = frozenset({"create_order", "verify_identity", "second_mention", "send_sms", "decompose"})


def tier_sequence(total: int) -> list[str]:
    """Deterministic tier allocation: the mix above, largest remainder, in a
    fixed order so two runs of one seed produce one corpus."""
    counts = {tier: total * share // 100 for tier, share in TIER_MIX}
    remainder = total - sum(counts.values())
    for tier, _ in sorted(TIER_MIX, key=lambda t: -t[1]):
        if remainder <= 0:
            break
        counts[tier] += 1
        remainder -= 1
    out: list[str] = []
    for tier, _ in TIER_MIX:
        out.extend([tier] * counts[tier])
    return out


def generate(seed: int, created_at: str) -> list[Case]:
    pools = load_pools()
    cases: list[Case] = []
    seen: set[str] = set()
    for family, registers in PLAN.items():
        builder = BUILDERS[family]
        index = 0
        for register, count in registers.items():
            tiers = tier_sequence(count) if family in NAMED_FAMILIES else ["common"] * count
            for tier in tiers:
                index += 1
                # One stream per case, derived from the seed and the case's
                # place in the plan: adding a family later does not reshuffle
                # the values of the families before it.
                rng = random.Random(f"{seed}:{family}:{register}:{index}")
                case = builder(pools, rng, register, tier, index, created_at, seed)
                digest = content_digest(case)
                while digest in seen:
                    rng = random.Random(f"{seed}:{family}:{register}:{index}:{digest}")
                    case = builder(pools, rng, register, tier, index, created_at, seed)
                    digest = content_digest(case)
                seen.add(digest)
                cases.append(case)
    return cases


def write(cases: list[Case], out: Path) -> None:
    for case in cases:
        dump(case, out / case.family / f"{case.id}.json")


def _same_tree(left: Path, right: Path) -> list[str]:
    differences: list[str] = []
    left_files = {p.relative_to(left) for p in left.rglob("*.json")}
    right_files = {p.relative_to(right) for p in right.rglob("*.json")}
    for missing in sorted(left_files - right_files):
        differences.append(f"only in {left}: {missing}")
    for extra in sorted(right_files - left_files):
        differences.append(f"only in {right}: {extra}")
    for shared in sorted(left_files & right_files):
        if not filecmp.cmp(left / shared, right / shared, shallow=False):
            differences.append(f"differs: {shared}")
    return differences


def _utf8_stdout() -> None:
    """Печатать по-русски в консоль Windows.

    Windows отдаёт стандартному выводу кодировку страницы (cp1251/cp437), и
    первая же русская строка роняет процесс с UnicodeEncodeError — что и
    случилось в первом же прогоне CI. Матрица ubuntu+windows стоит в CI
    ровно ради таких находок, и чинить это надо не переменной окружения в
    workflow, а здесь: читатель статьи запустит бенчмарк у себя, и у него
    тоже Windows.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def main() -> int:
    _utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out", required=True, help="directory the cases are written to")
    parser.add_argument("--created", default=dt.date.today().isoformat(), help="the created_at stamp on every case")
    parser.add_argument("--check", action="store_true", help="regenerate elsewhere and compare instead of writing")
    args = parser.parse_args()
    out = Path(args.out)

    if args.check:
        existing = load_dir(out)
        created = existing[0].created_at if existing else args.created
        cases = generate(args.seed, created)
        with tempfile.TemporaryDirectory() as tmp:
            fresh = Path(tmp) / "cases"
            write(cases, fresh)
            differences = _same_tree(out, fresh)
        if differences:
            print(f"corpus does not match seed {args.seed}:", file=sys.stderr)
            for line in differences[:40]:
                print("  " + line, file=sys.stderr)
            if len(differences) > 40:
                print(f"  … and {len(differences) - 40} more", file=sys.stderr)
            return 1
        print(f"corpus matches seed {args.seed}: {len(cases)} cases")
        return 0

    cases = generate(args.seed, args.created)
    problems = [(case.id, p) for case in cases for p in validate(case)]
    if problems:
        for case_id, problem in problems[:40]:
            print(f"{case_id}: {problem}", file=sys.stderr)
        print(f"{len(problems)} problems; nothing written", file=sys.stderr)
        return 1
    if out.exists():
        shutil.rmtree(out)
    write(cases, out)
    by_family: dict[str, int] = {}
    for case in cases:
        by_family[case.family] = by_family.get(case.family, 0) + 1
    print(f"{len(cases)} cases -> {out}")
    for family, count in sorted(by_family.items()):
        print(f"  {family:16s} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
