"""The checks a contributed case must pass, and the check the benchmark
itself must pass.

WHY A BENCHMARK NEEDS GATES OF ITS OWN. A corpus can be built so that it
cannot fail — a selection rule that uses the detector's own signals, value
pools drawn from the detector's own dictionary, a scorer that returns True
over an empty list. Each of those has happened to somebody, and none is
visible in the numbers: the benchmark simply reports a high score for
everyone and nobody learns anything. These gates are mechanical checks
against that class of defect, run on every pull request.

G6 AND G7 ARE THE INTERESTING ONES. G6 runs the passthrough and demands a
perfect end-to-end line: if a value cannot survive a masker that changes
nothing, the CASE is wrong. G7 runs the naive regex masker and demands it
leave a mark on every case that is not explicitly marked `hard` — a corpus
where the naive baseline scores the same as the passthrough is a corpus
that discriminates nothing.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from agentmask_ru.adapters.reference import NoopMasker, PlaceholderMasker
from agentmask_ru.harness import run
from agentmask_ru.schema import Case, load_dir, validate
from agentmask_ru.score import score

# Shares the corpus must satisfy, so a plan change cannot quietly empty a
# stratum the report prints.
MAX_HARD_SHARE = 0.5
NAME_TIER_BOUNDS: tuple[float, float] = (0.25, 0.60)     # share of NAME items outside the common tier
MIN_REGISTER_SHARE = 0.20
MIN_FAMILY_CASES = 30
MIN_NO_CUE_NAME_SHARE = 0.30


@dataclass(frozen=True)
class GateResult:
    name: str
    ok: bool
    detail: str


def _g1_schema(root: Path) -> GateResult:
    """Каждый файл случая — по JSON-схеме.

    Схема и `schema.py` описывают одно и то же с двух сторон, и гейт нужен
    ровно потому, что они могут разойтись: человек правит датакласс и
    забывает схему, а корпус собирают внешние люди по схеме.
    """
    import json

    from jsonschema import Draft202012Validator

    path = root / "schema" / "case.schema.json"
    if not path.exists():
        return GateResult("G1 файлы случаев по схеме", False, f"нет {path}")
    validator = Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))
    problems: list[str] = []
    for case_path in sorted((root / "cases").rglob("*.json")):
        raw = json.loads(case_path.read_text(encoding="utf-8"))
        for error in validator.iter_errors(raw):
            problems.append(f"{case_path.name}: {error.message[:100]}")
            break
    ok = not problems
    detail = "все файлы по схеме" if ok else "; ".join(problems[:4])
    return GateResult("G1 файлы случаев по схеме", ok, detail)


def _g2_g5_per_case(cases: list[Case]) -> list[GateResult]:
    problems: list[str] = []
    for case in cases:
        for problem in validate(case):
            problems.append(f"{case.id}: {problem}")
    ok = not problems
    detail = "все случаи структурно верны" if ok else "; ".join(problems[:5]) + (f" (+{len(problems) - 5})" if len(problems) > 5 else "")
    return [GateResult("G2-G5 структура случая", ok, detail)]


def _g6_identity(cases: list[Case]) -> GateResult:
    observations = run(NoopMasker(), cases, "copier", 0)
    scores = score(observations)
    leak = scores.lines["leak"]
    end_to_end = scores.lines["end_to_end"]
    overmask = scores.lines["overmask"]
    broken = [o.case_id for o in observations for i in o.items if i.round_trip is False]
    ok = leak.hits == 0 and end_to_end.hits == end_to_end.total and overmask.hits == overmask.total and end_to_end.total > 0
    detail = (f"passthrough: leak {leak.hits}/{leak.total}, end_to_end {end_to_end.hits}/{end_to_end.total}, "
              f"overmask {overmask.hits}/{overmask.total}")
    if broken:
        detail += f"; эталон недостижим в {sorted(set(broken))[:5]}"
    return GateResult("G6 passthrough проходит корпус", ok, detail)


def _g7_reference_differs(cases: list[Case]) -> GateResult:
    observations = run(PlaceholderMasker(), cases, "copier", 0)
    unmarked: list[str] = []
    for observation, case in zip(observations, cases):
        touched = any(item.altered for item in observation.items)
        if not touched and not observation.hard:
            unmarked.append(case.id)
    scores = score(observations)
    leak = scores.lines["leak"]
    ok = not unmarked and leak.hits > 0
    detail = f"наивный regex изменил {leak.hits}/{leak.total} значений"
    if unmarked:
        detail += f"; не отмечены hard и не тронуты: {unmarked[:5]}" + (f" (+{len(unmarked) - 5})" if len(unmarked) > 5 else "")
    return GateResult("G7 эталонный маскер отличим от passthrough", ok, detail)


def _g8_strata(cases: list[Case]) -> GateResult:
    problems: list[str] = []
    hard_share = sum(1 for c in cases if c.hard) / len(cases)
    if hard_share > MAX_HARD_SHARE:
        problems.append(f"hard {hard_share:.0%} > {MAX_HARD_SHARE:.0%}")
    names = [item for case in cases for item in case.pii if item.type == "NAME"]
    if names:
        outside = sum(1 for item in names if item.tier != "common") / len(names)
        low, high = NAME_TIER_BOUNDS
        if not low <= outside <= high:
            problems.append(f"имена вне частотного яруса {outside:.0%}, нужно {low:.0%}–{high:.0%}")
        no_cue = sum(1 for item in names if not item.cue) / len(names)
        if no_cue < MIN_NO_CUE_NAME_SHARE:
            problems.append(f"имён без подсказки {no_cue:.0%} < {MIN_NO_CUE_NAME_SHARE:.0%}")
    for register in {c.register for c in cases}:
        share = sum(1 for c in cases if c.register == register) / len(cases)
        if share < MIN_REGISTER_SHARE:
            problems.append(f"регистр {register}: {share:.0%} < {MIN_REGISTER_SHARE:.0%}")
    for family in {c.family for c in cases}:
        count = sum(1 for c in cases if c.family == family)
        if count < MIN_FAMILY_CASES:
            problems.append(f"семья {family}: {count} < {MIN_FAMILY_CASES}")
    ok = not problems
    return GateResult("G8 страты наполнены", ok, "; ".join(problems) if problems else "все страты в границах")


# An import statement, at the start of a line — so this gate does not flag
# the pattern it is written with.
_PRIVATE_IMPORT = re.compile(r"^\s*(?:import|from)\s+(pseudex|licensing)\b", re.MULTILINE)


def _g10_no_private_imports(root: Path) -> GateResult:
    hits: list[str] = []
    for path in sorted((root / "src").rglob("*.py")):
        for match in _PRIVATE_IMPORT.finditer(path.read_text(encoding="utf-8")):
            hits.append(f"{path.relative_to(root)}: {match.group(0).strip()}")
    return GateResult("G10 нет импортов из закрытого движка", not hits, "; ".join(hits) if hits else "src/ чист")


def _g11_results(root: Path, cases: list[Case]) -> GateResult:
    from agentmask_ru.results import corpus_digest

    digest = corpus_digest(cases)
    stale: list[str] = []
    for path in sorted((root / "results").rglob("*.json")):
        # `results/_archive/` holds runs WITHDRAWN on a corpus bump — kept in
        # git so a published number stays checkable, ignored here and by the
        # leaderboard, because they were measured on a corpus that no longer is.
        if "_archive" in path.parts:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        found = str(payload.get("manifest", {}).get("corpus_digest", ""))
        if found != digest:
            stale.append(f"{path.relative_to(root)} ({found or 'нет'} ≠ {digest})")
    return GateResult("G11 результаты считаны на текущем корпусе", not stale,
                      "; ".join(stale) if stale else f"дайджест корпуса {digest}")


def run_gates(root: Path, cases: list[Case]) -> list[GateResult]:
    results = [_g1_schema(root)]
    results += _g2_g5_per_case(cases)
    results.append(_g6_identity(cases))
    results.append(_g7_reference_differs(cases))
    results.append(_g8_strata(cases))
    results.append(_g10_no_private_imports(root))
    results.append(_g11_results(root, cases))
    return results


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


def main(argv: list[str] | None = None) -> int:
    _utf8_stdout()
    parser = argparse.ArgumentParser(description="Проверки корпуса и репозитория")
    parser.add_argument("--cases", default="cases", help="каталог со случаями")
    parser.add_argument("--root", default=".", help="корень репозитория")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    cases = load_dir(Path(args.cases))
    if not cases:
        print("случаев не найдено", file=sys.stderr)
        return 1
    failures = 0
    for result in run_gates(root, cases):
        mark = "OK  " if result.ok else "FAIL"
        print(f"{mark} {result.name}: {result.detail}")
        failures += 0 if result.ok else 1
    print(f"\n{len(cases)} случаев, провалено проверок: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
