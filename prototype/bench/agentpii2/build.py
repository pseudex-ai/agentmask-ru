"""Assemble AgentPII-RU v2 from its eight family generators, and refuse to write
a corpus that does not validate.

WHAT THIS FILE OWNS AND WHAT IT DOES NOT. Every family generator owns its own
text, spans, canonical forms and claims; this file owns the MIX, the file order,
the validation gate and the frozen tier ladder. It deliberately does not repair
anything a family produced: a defect fixed here would be a defect the family's
own self-check still passes, and the next regeneration would bring it back.

THE DISTRIBUTION, and it is the design doc's (§3) with two forced adjustments:

    transfer  450   the only family where a per-TYPE rate is estimable. 10
                    scenarios x 5 registers x 3 difficulties x 3 sets, and the
                    generator refuses an off-grid count because CARD and PLATE
                    live in one scenario each — 45 gold values, 9 per register,
                    only just above the suppression floor of five.
    length    150   3 rungs x 5 registers x 10. The only rung where the mask
                    cache, `content_key`'s conversation component and the
                    already-minted-token rule are load-bearing at all.
    result    150   3 result shapes x 5 registers x 10.
    compare   100   place / person, the only number the linking mechanism gets.
    indirect  100   address / person, the tool -> model -> tool path, which
                    shares no code with the user -> model -> tool one but a vault.
    rank       60   4 relations x 5 registers x 3, `frequency` the control arm.
    scope      60   2 directions x 3 vehicles x 5 registers, in pairs.
    speech     96   NOT the doc's 111. The family is 122 hand-annotated real
                    utterances, and 15 of them are bare streets whose only claim
                    is `optional` — unfalsifiable alone, by the schema's own
                    definition — so each travels with a real negative utterance
                    as a second turn. Nothing is dropped or double-counted.
                                       ----
                    1166 cases

Why not more of the cheap families: every one of them is generated from a
template pool, and doubling `compare` buys a hundred more draws from the same
twelve sentences. Perlitz et al. (*Efficient Benchmarking*, arXiv 2308.11696) is
the rule the doc already adopted — maximise the coverage of each source of
variation rather than exhausting the cross-product — and the sources of variation
here are the families and the registers, both of which are already saturated.

FILE ORDER IS PROPORTIONAL INTERLEAVING, not family-major. Measured on v1:
`bench/agentrun/runner.py --limit 150` over a scenario-major file reached 4 of 10
scenarios and none of the six main ones, and printed a number that reads like a
product number. Each family's cases are laid out at even fractions of the file,
so any prefix holds every family in roughly its corpus proportion — while each
family's INTERNAL order is preserved, which is what keeps `scope`'s lead cases
ahead of the follows that name them.

THE REFUSAL, and it has two levels because two kinds of problem exist.

    HARD    `schema.validate` on every case and `schema.validate_corpus` on the
            whole. Nothing is written. A ground truth that disagrees with its own
            text keeps producing numbers, and offsets are the part that rots
            first because every register transform rewrites the string.
    ADVISORY  tool-schema drift, derived-scope collisions and cross-family value
            collisions. These break no case — each is internally consistent and
            scoreable — but each weakens a claim the CORPUS makes, so they are
            printed with names and counts and the file is still written. Turning
            an advisory into a refusal would leave the corpus unbuildable for a
            reason no case is responsible for; hiding it would leave a number
            nobody can attribute.

SPEECH IS VALIDATED HYDRATED AND WRITTEN DRY. Its 122 utterances are OpenSTT
`asr_calls_2_val` under CC BY-NC 4.0: measuring with them is allowed, shipping
them is not. So `validate` runs against the filled-in text — offsets cannot be
checked otherwise — and the file carries `Source` references with empty content.
`schema.validate` refuses a message that names a source AND carries its text, so
a mistaken commit of licensed material is a build failure rather than a licence
violation somebody else discovers.
"""

import argparse
import json
import random
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bench.agentpii2 import tools  # noqa: E402
from bench.agentpii2.families import (  # noqa: E402
    carryover, comparison, context, dispatch, indirect, scope, speech,
    toolresult,
)
from bench.agentpii2.schema import (  # noqa: E402
    FAMILIES, REGISTERS, Case, ExpectedCall, Ladder, LinkExpectation, Negative,
    PiiItem, case_characters, corpus_digest, message_text, type_denominators,
    validate, validate_corpus,
)

HERE = Path(__file__).resolve().parent
CORPUS = HERE / "corpus.json"
LADDER = HERE / "ladder.json"
SEED = 20260830

# module, count, and the families the module emits. The count is what the
# generator is ASKED for; `speech` is the only one that can return fewer, and it
# raises rather than padding real speech with generated speech.
PLAN: tuple[tuple[str, object, int], ...] = (
    ("carryover", carryover, 450),
    ("context", context, 150),
    ("comparison", comparison, 100),
    ("indirect", indirect, 100),
    ("toolresult", toolresult, 210),
    ("scope", scope, 60),
    ("speech", speech, 96),
    ("dispatch", dispatch, 168),
)


def generate(seed: int) -> list[Case]:
    """Every family, interleaved proportionally.

    EACH FAMILY GETS ITS OWN `random.Random`, seeded from the run seed and its
    own name. A single shared generator would make every family's output depend
    on how many draws the families before it happened to make, so adding one
    template to `transfer` would silently redraw all of `compare`, and the corpus
    would stop being comparable to its own previous version for a reason that has
    nothing to do with the corpus.
    """
    produced: list[list[Case]] = []
    for name, module, count in PLAN:
        stream = random.Random(f"{seed}:{name}")
        produced.append(list(module.build(stream, count)))  # type: ignore[attr-defined]

    # PROPORTIONAL INTERLEAVING. Case i of a family of n sits at fraction
    # (i + 0.5) / n; sorting every case by that fraction spreads each family
    # evenly over the whole file and preserves each family's internal order,
    # because the fractions inside one family are already increasing. A plain
    # round-robin would drain `rank` (60 cases) in the first tenth and leave the
    # tail entirely `transfer`.
    ordered: list[tuple[float, int, int, Case]] = []
    for family_index, cases in enumerate(produced):
        for position, case in enumerate(cases):
            ordered.append(((position + 0.5) / len(cases), family_index,
                            position, case))
    ordered.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in ordered]


def hydrated(cases: list[Case]) -> list[Case]:
    """The corpus with licensed text filled in, for validation and scoring only.

    Dispatches by `Source.corpus`, which is the schema's own contract. It does
    not call `schema.hydrate`: that function rebuilds the case through
    `Case(**asdict(case))` and `asdict` recurses, so every `PiiItem` comes back
    as a plain dict and the result cannot be validated or scored, and it keeps
    the `source` key beside the text it just filled in, which trips the same
    validator's rule that a message naming a licensed source must ship empty.
    Both are defects in the schema, reported here and not repaired here.
    """
    filled: list[Case] = []
    for case in cases:
        if not any(isinstance(m.get("source"), dict) for m in case.messages):
            filled.append(case)
            continue
        filled.extend(speech.hydrated([case]))
    return filled


# --- advisory checks, none of which can fail a single case ------------------

def derived_scope_collisions(cases: list[Case]) -> list[str]:
    """Two cases with no `conversation_id` whose first two messages are equal.

    The engine derives a conversation identity from the first TWO messages when
    the caller names none (`conversation_key`), and a system prompt is shared by
    every dialogue an agent has, so two cases opening identically ARE one
    conversation as far as the vault is concerned and one customer's partial
    mention would resolve against another's full one. That is a corpus bug which
    reports as a gateway leak, and it is invisible to a per-case validator
    because each case is individually correct.
    """
    problems: list[str] = []
    seen: dict[str, str] = {}
    for case in cases:
        if case.conversation_id:
            continue
        opening = " ".join(message_text(case, index)
                           for index in range(min(2, len(case.messages))))
        if opening in seen:
            problems.append(f"{case.id} opens identically to {seen[opening]} and "
                            f"both derive their conversation id from the "
                            f"transcript; they would share one scope")
        seen[opening] = case.id
    return problems


def value_collisions(cases: list[Case]) -> list[str]:
    """One canonical value claimed by two families.

    The whole corpus is scored through ONE tenant vault, and the vault is keyed
    `(customer, canonical)`. A value that two families both mint therefore
    reaches one substitute in both: harmless where the claim is `same`, and
    exactly what a `different` claim forbids. Reported per value rather than per
    case, and only where two FAMILIES are involved, because inside a family the
    author already decided what shares an identity.
    """
    owners: dict[tuple[str, str], set[str]] = {}
    claimed_apart: set[tuple[str, str]] = set()
    for case in cases:
        apart = {link.left for link in case.links if link.kind == "different"}
        for item in case.pii:
            if not item.canonical:
                continue
            key = (item.type, item.canonical.casefold())
            owners.setdefault(key, set()).add(case.family)
            if item.id in apart:
                claimed_apart.add(key)
    problems: list[str] = []
    for key, families in sorted(owners.items()):
        if len(families) < 2:
            continue
        kind, value = key
        note = ("a `different` link is claimed on it" if key in claimed_apart
                else "no `different` claim rests on it")
        problems.append(f"{kind} {value!r} is minted by {sorted(families)}, one "
                        f"vault key for both ({note})")
    return problems


# --- the frozen tier ladder -------------------------------------------------

def build_ladder(cases: list[Case], version: int, seed: int) -> Ladder:
    """One frozen ordering whose every prefix is as balanced as it can be.

    NOT A SAMPLER, and that is the whole design. Every named subset in the field
    is a frozen id list (SWE-bench Lite is 300 named instances, BIG-bench Lite is
    24 named tasks), and measured on v1's corpus, re-running a balanced sampler
    after growing the corpus by 10% kept only 3-4 of 10 nano cases: the better a
    sampler balances, the more violently it redraws, because balance is a global
    property. Freezing is what makes last month's number comparable to this one.

    THE PRIORITY IS THE DESIGN DOC'S, in this order and no other: a hard floor of
    one case per family, then register balance, then difficulty free and only
    printed. Checked on v1: stratifying by family alone drops `sloppy` out of
    `nano` entirely, and `sloppy` is the measurably weakest register, so the
    smallest tier would systematically flatter the gateway.

    `seed` decides nothing but the tie-break, and the tie-break is by case id
    rather than by draw, so the ladder is reproducible from the corpus alone.
    """
    remaining = {case.id: case for case in cases}
    family_count: dict[str, int] = {name: 0 for name in FAMILIES}
    register_count: dict[str, int] = {name: 0 for name in REGISTERS}
    order: list[str] = []
    while remaining:
        best = min(
            remaining.values(),
            key=lambda case: (family_count[case.family],
                              register_count[case.register],
                              case.id))
        order.append(best.id)
        family_count[best.family] += 1
        register_count[best.register] += 1
        del remaining[best.id]
    return Ladder(version=version, seed=seed,
                  corpus_sha256=corpus_digest(cases), order=order)


# --- the file ---------------------------------------------------------------

def to_json(cases: list[Case], seed: int) -> dict[str, object]:
    return {
        "benchmark": "AgentPII-RU",
        "version": 2,
        "seed": seed,
        # The digest a `Ladder` is pinned to, written here so a consumer can
        # check the pair without recomputing over a file it may have edited.
        "corpus_sha256": corpus_digest(cases),
        "cases": [case.to_json() for case in cases],
    }


def load(path: Path) -> list[Case]:
    """Read the corpus back as `Case` objects, licensed text still absent.

    A LOADER IS PART OF THE FORMAT, not a convenience. `json.load` gives nested
    dicts, and every function in `schema.py` that a scorer must use, from
    `validate` to `type_denominators`, reads attributes. A scorer left to
    reconstruct the dataclasses itself reconstructs them slightly differently,
    and the first thing to go is the `duty` field that separates a leak from a
    permitted mask.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases: list[Case] = []
    for row in payload["cases"]:
        row = dict(row)
        row["pii"] = [PiiItem(**item) for item in row["pii"]]
        row["negatives"] = [Negative(**item) for item in row["negatives"]]
        row["links"] = [LinkExpectation(**item) for item in row["links"]]
        row["calls"] = [ExpectedCall(**item) for item in row["calls"]]
        cases.append(Case(**row))
    return cases


# --- the report -------------------------------------------------------------

# THE REGISTER WEIGHTS ARE A CLAIM ABOUT TRAFFIC AND THE CELLS ARE NOT. The
# corpus is built uniform so that a per-register rate is estimable with equal
# precision; the owner's requirement, that literary text be RARE, is a statement
# about traffic and is met by `schema.REGISTER_WEIGHTS`, which puts `clean` at
# 0.05. Both totals are printed by any scorer that uses `register_weighted`.
# What this report prints is the CELL count, so the difference between the two
# statements stays visible instead of being settled here.
_LITERARY: frozenset[str] = frozenset({"clean"})


# Families whose register is dictated by their source rather than chosen.
_REAL_TEXT: frozenset[str] = frozenset({"speech", "dispatch"})


def _distinct_values(cases: list[Case]) -> dict[str, int]:
    """Distinct gold values per type, printed beside the item count.

    A rate over 1675 NAME items whose 393 distinct people each recur four times
    has the error bars of 393 draws, not 1675 — the repeats are the same string
    put to the same detector, so they carry no independent information, and a
    confidence interval over the larger number lies in our favour. Printed for
    the same reason `type_denominators` suppresses small rates: a denominator
    that looks big enough and is not. Case-folded, because «Иванов» and
    «иванов» are one value said in two registers, not two draws.
    """
    seen: dict[str, set[str]] = {}
    for case in cases:
        for item in case.pii:
            if item.duty == "required":
                seen.setdefault(item.type, set()).add(item.value.casefold())
    return {kind: len(values) for kind, values in seen.items()}


def report(cases: list[Case]) -> None:
    families: dict[str, int] = {}
    registers: dict[str, int] = {}
    scenarios: dict[str, set[str]] = {}
    rungs: dict[str, int] = {}
    duties: dict[str, int] = {"required": 0, "optional": 0}
    links: dict[str, int] = {}
    negatives = calls = 0
    for case in cases:
        families[case.family] = families.get(case.family, 0) + 1
        registers[case.register] = registers.get(case.register, 0) + 1
        rungs[case.length_rung] = rungs.get(case.length_rung, 0) + 1
        scenarios.setdefault(case.family, set()).add(case.scenario)
        negatives += len(case.negatives)
        calls += len(case.calls)
        for item in case.pii:
            duties[item.duty] = duties.get(item.duty, 0) + 1
        for link in case.links:
            links[link.kind] = links.get(link.kind, 0) + 1

    sizes = [case_characters(case) for case in cases]
    print(f"cases {len(cases)}   messages "
          f"{sum(len(case.messages) for case in cases)}   characters "
          f"{sum(sizes)}")
    print()
    print("по семействам")
    for name in FAMILIES:
        count = families.get(name, 0)
        flag = "" if count else "   <-- MISSING"
        print(f"   {name:<10} {count:>5}   сценариев "
              f"{len(scenarios.get(name, ())):>3}{flag}")
    print()
    print("по регистрам (ячейки равные по построению; вес трафика отдельно)")
    for name in REGISTERS:
        count = registers.get(name, 0)
        share = 100.0 * count / len(cases)
        mark = "  литературный" if name in _LITERARY else ""
        print(f"   {name:<10} {count:>5}   {share:5.1f}%{mark}")
    literary = sum(registers.get(name, 0) for name in _LITERARY)
    print(f"   литературного текста {literary} из {len(cases)} "
          f"({100.0 * literary / len(cases):.1f}%)")
    # THE GRID IS UNIFORM ONLY OVER THE FAMILIES THAT CHOOSE THEIR REGISTER.
    # `speech` and `dispatch` are real recordings and their register is a
    # property of the source, not a cell we fill — every case is `voice_raw` and
    # no amount of balancing changes that. Printed apart because one blended
    # percentage would read as a broken design rather than as two designs, and
    # because a scorer applying REGISTER_WEIGHTS to the blend weights real
    # speech as though we had chosen how much of it to write.
    synthetic = [case for case in cases if case.family not in _REAL_TEXT]
    real = [case for case in cases if case.family in _REAL_TEXT]
    print(f"   синтетические семейства {len(synthetic)} кейсов — "
          f"ячейки равные: "
          f"{', '.join(str(sum(1 for case in synthetic if case.register == name)) for name in REGISTERS)}")
    print(f"   реальная речь {len(real)} кейсов — весь voice_raw по источнику, "
          f"не по выбору")
    print()
    print("по типам ПД (только duty=required; знаменатель < 5 печатается счётом)")
    print("   тип         значений  различных  повтор")
    distinct = _distinct_values(cases)
    for kind, count in sorted(type_denominators(cases).items(),
                              key=lambda row: -row[1]):
        unique = distinct[kind]
        print(f"   {kind:<10} {count:>8}  {unique:>9}   {count / unique:4.1f}x"
              f"{'   <-- ниже порога подавления' if count < 5 else ''}")
    print()
    print(f"ступени длины  {rungs}")
    print(f"эталонных значений  required {duties['required']}  "
          f"optional {duties['optional']}")
    print(f"негативов {negatives}   ожидаемых вызовов {calls}   связей {links}")
    given = sum(1 for case in cases if case.conversation_id)
    print(f"conversation_id: задан {given}, выводится {len(cases) - given}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", default=str(CORPUS))
    parser.add_argument("--ladder-out", default=str(LADDER))
    parser.add_argument("--ladder-version", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true",
                        help="validate and report, write nothing")
    args = parser.parse_args()

    cases = generate(args.seed)
    # VALIDATED HYDRATED, WRITTEN DRY. Offsets in the `speech` family cannot be
    # checked against text the corpus is not licensed to carry, so validation
    # runs over the filled-in copy and the file gets the references.
    filled = hydrated(cases)

    problems = [problem for case in filled for problem in validate(case)]
    problems.extend(validate_corpus(filled))
    if problems:
        print(f"ОТКАЗ: {len(problems)} проблем, файл не записан", file=sys.stderr)
        for problem in problems[:60]:
            print(f"   {problem}", file=sys.stderr)
        if len(problems) > 60:
            print(f"   ... и ещё {len(problems) - 60}", file=sys.stderr)
        return 1

    report(filled)

    advisories: list[tuple[str, list[str]]] = [
        ("схемы инструментов расходятся между семействами", tools.drift(cases)),
        ("столкновения выводимой области разговора",
         derived_scope_collisions(filled)),
        ("одно каноническое значение у двух семейств", value_collisions(cases)),
    ]
    for title, found in advisories:
        print()
        if not found:
            print(f"{title}: нет")
            continue
        print(f"{title}: {len(found)}")
        for line in found[:25]:
            print(f"   {line}")
        if len(found) > 25:
            print(f"   ... и ещё {len(found) - 25}")

    if args.dry_run:
        print("\n--dry-run: ничего не записано")
        return 0

    ladder = build_ladder(cases, args.ladder_version, args.seed)
    Path(args.out).write_text(
        json.dumps(to_json(cases, args.seed), ensure_ascii=False, indent=1),
        encoding="utf-8")
    Path(args.ladder_out).write_text(
        json.dumps({"version": ladder.version, "seed": ladder.seed,
                    "corpus_sha256": ladder.corpus_sha256,
                    "order": ladder.order},
                   ensure_ascii=False, indent=1),
        encoding="utf-8")

    # THE FILE MUST READ BACK AS WHAT WAS VALIDATED. A loader that reconstructs
    # the dataclasses slightly differently is the defect the schema's own
    # `hydrate` already has, and it would be discovered by a scorer months later.
    reloaded = load(Path(args.out))
    if [case.to_json() for case in reloaded] != [case.to_json() for case in cases]:
        print("ОТКАЗ: перечитанный корпус не совпадает с записанным",
              file=sys.stderr)
        return 1
    print(f"\n{args.out}  ({Path(args.out).stat().st_size // 1024} КБ)")
    print(f"{args.ladder_out}  лестница v{ladder.version}, "
          f"корпус {ladder.corpus_sha256[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
