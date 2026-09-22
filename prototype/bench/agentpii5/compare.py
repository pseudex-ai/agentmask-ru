"""ЛЮБОЙ ПРОГОН ПРОТИВ ЛЮБОГО — строки обоих, разница, и что отделяет её от нуля.

    python3 -m bench.agentpii5.compare <прогон A> <прогон B>
    python3 -m bench.agentpii5.compare <A> <B> --cases --top 40
    python3 -m bench.agentpii5.compare <A> <B> --across-corpora

Spec `docs/tz-bench-harness.md` §2.1, §2.2, §2.4 (items 5, 6, 8). No model, no
network, no keys: everything is read from the files of a finished run
(`contracts.RUN_FILES`).

NEITHER SIDE IS THE BASELINE. `bench/agentpii4/compare_runs.py` prints columns
headed «до» and «после» and so decides for the reader which run is the right
one; here the sides are A and B, the difference is B − A and the header says
so. Engine A against engine B, version against version, before and after a
fix — one command, and it does not know which of those is happening.

FOUR RULES HOLD THE HONESTY HERE, AND EVERY ONE WAS PAID FOR ELSEWHERE.

  1. **The shared basis is declared, not assumed.** Lines are computed over the
     INTERSECTION of case ids; each population's size and the «only in A» /
     «only in B» lists are printed in the header. A run on another corpus is
     REFUSED until `--across-corpora` is passed, and then the header says how
     many shared ids the comparison rests on. Two populations quietly summed
     into one difference is a comparison of corpora sold as a comparison of
     engines.
  2. **«Comparable» is declared FOR EVERY LINE.** v4's lesson №1: a triple with
     nothing to compare passed all five levels, because `all([])` is True. A
     case whose denominator for a line is zero in either run is OUT of the
     paired statistic and inside the printed `сравнимо k/K`. Zero comparable
     cases is «nothing to compare», never «no difference».
  3. **The decomposition by case is CHECKED.** A paired interval needs the line
     to be the sum of its cases; a metric whose per-case sum is not the line
     over the whole population (something counted across a case boundary)
     prints the difference and REFUSES the interval with the reason named.
     Summing a non-additive metric silently means drawing an interval around a
     number nobody computed.
  4. **«Not distinguishable from zero» is NOT «equivalent».** It is the absence
     of evidence of a difference, not evidence of its absence; equivalence is
     what TOST at δ=3pp proves in the run's own report, and the word
     «эквивалентно» is never printed here
     (`test_compare.test_no_equivalence_claim`). The 1/n resolution floor is
     kept: a percentile bootstrap over identical cases returns a zero-width
     interval, and zero width certifies ANY margin — v4's lesson, learned in
     `stats.tost_equivalence` and repeated here for the difference of two runs.

WHAT COMPUTES WHAT. The bootstrap is `bench/agentpii4/stats.py::
cluster_bootstrap`, called as it stands, with no wrapper and no copy: a cluster
is a shared PERSONAL VALUE (`Case.cluster`), so one phone in three cases is one
draw. `stats.CaseEffect` is v4's paired counter; here its `ic`/`cc` hold TWO
RUNS' hits on one case and `n` their shared denominator, so `(ic − cc)/n` is
exactly that case's difference of rates (see `paired_effects`). The line
definitions come from `report.py` and `metrics.METRIC_FUNCTIONS`; the v4 levels
from `bench/agentpii4/report.py::case_effects`. Nothing is redefined: a line
the report's gate refused to print is not printed here either.
"""
import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from bench.agentpii4 import report as v4_report
from bench.agentpii4 import stats
from bench.agentpii4.autopsy import _load_run
from bench.agentpii4.report import Scored
from bench.agentpii4.schema import Case
from bench.agentpii5 import contracts, report
from bench.agentpii5.contracts import Line, Metric, MetricRegistry, RunObservation
from bench.agentpii5.metrics import METRIC_FUNCTIONS

# The C′≈C column of a v4 level, printed as a line of its own beside the I≈C
# one. Two lines and not one number because a move in I≈C that the control arm
# made too is arm noise and not the gateway's doing — v4 subtracts it inside
# one run, and a reader comparing two RUNS needs to see both halves move.
CONTROL_SUFFIX: str = "~контроль"
# Reps and seed of the bootstrap. 1000 and not v4's report default of 4000
# because this tool runs ~35 lines instead of 6 and is read interactively;
# `--reps` is the knob, and the value is printed in the header so two
# comparisons cannot silently be made at different resolutions.
DEFAULT_REPS: int = 1000
DEFAULT_SEED: int = 0
# The three verdicts a difference can get. Spelled once so the renderer, the
# tests and any later reader cannot disagree about the words — and so that the
# absence of «эквивалентно» is a property of a constant, not of a format string.
SIGNIFICANT: str = "различие значимо"
INDISTINGUISHABLE: str = "не отличимо от нуля"
NOTHING_TO_COMPARE: str = "нечего сравнивать"


class CompareError(ValueError):
    """Two directories that cannot be compared, with the reason named.

    Raised instead of printing: a comparison of runs that do not share a
    corpus, or of a directory that is not a run, produces numbers whose
    difference means something other than what the header would claim.
    """


# --- reading one side ------------------------------------------------------------------

@dataclass(frozen=True)
class RunSide:
    """ONE run directory, read once, with everything both halves of the
    comparison need.

    `levels` is v4's own per-case decomposition of each paired level
    (`v4_report.case_effects`), kept rather than recomputed: the v5 lines and
    the v4 levels then come from the two modules that define them, and this
    file defines neither.
    """

    run_dir: Path
    run_id: str
    corpus_digest: str
    cases: dict[str, Case]
    observations: tuple[RunObservation, ...]
    levels: dict[str, dict[str, stats.CaseEffect]]
    hopless: tuple[str, ...]
    stopped: tuple[str, ...]
    meta: dict[str, object]


def corpus_digest(run_dir: Path) -> str:
    """The digest the run's own v5 corpus snapshot carries.

    NOT `report._digest`, and the difference is the whole point of §2.1: that
    helper returns "" both for «no corpus file» and for «a corpus that names no
    digest», and a comparison must tell those apart — the first is «this is not
    a run», the second is «these runs cannot be certified to share a corpus».
    """
    path = run_dir / "corpus.v5.json"
    if not path.exists():
        raise CompareError(f"{run_dir}: нет corpus.v5.json — это не каталог прогона v5")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise CompareError(f"{path}: ожидался объект, найден {type(raw).__name__}")
    digest = raw.get("digest")
    if digest is None:
        return ""
    if not isinstance(digest, str):
        raise CompareError(f"{path}: digest должен быть строкой, найден {digest!r}")
    return digest


def read_side(run_dir: Path) -> RunSide:
    """Everything one run contributes to a comparison, through the readers that
    own each file.

    `_load_run` + `score_triples` is what `report.v4_half` does before it
    renders; `render` is NOT called here because its bootstraps cost minutes
    and this tool prints its own intervals. The observations come from
    `report.observations_of`, so a run whose `<run>.hops.jsonl` is missing is
    refused here exactly as the report refuses it — a comparison built on half
    a run would compare whichever half happened to be on disk.
    """
    # The digest FIRST, and that order is not cosmetic: `_load_run` falls back
    # to v4's own committed corpus when a directory carries no `corpus.json`,
    # so a path that is not a run at all gets three readers deep before anyone
    # says so. `corpus_digest` refuses it by name on the first line.
    digest = corpus_digest(run_dir)
    cases, triples, _excluded = _load_run(run_dir)
    scored: list[Scored] = v4_report.score_triples(cases, triples)
    half = report.observations_of(run_dir, scored, report.v5_cases(run_dir))
    levels: dict[str, dict[str, stats.CaseEffect]] = {}
    for level, _label in contracts.V4_LEVELS:
        levels[level] = {one.case_id: one for one in v4_report.case_effects(cases, scored, level)}
    run_id = report.run_id_of(run_dir)
    return RunSide(run_dir=run_dir, run_id=run_id, corpus_digest=digest,
                   cases=dict(cases), observations=half.observations, levels=levels,
                   hopless=half.hopless, stopped=half.stopped,
                   meta=report.meta_of(run_dir, run_id))


def case_ids(side: RunSide) -> set[str]:
    """The case ids this run has an OBSERVATION for — never the corpus's ids.

    A case in the corpus snapshot that no arm reached contributes to no line,
    and counting it as shared would put a case in the denominator of «общая
    основа» that neither run could say anything about.
    """
    return {one.case.base.id for one in side.observations}


# --- one line of one run ----------------------------------------------------------------

@dataclass(frozen=True)
class LineCells:
    """One metric line of one run over the shared basis, and its decomposition.

    `line` is the metric over ALL the shared observations — the number the
    report would print. `per_case` is the same metric over each case's
    observations alone, which is what the paired bootstrap needs.
    `decomposes` is False when the two disagree, and then the interval is
    refused with that reason instead of being drawn around a number nobody
    computed.
    """

    name: str
    line: Line
    per_case: dict[str, tuple[int, int]]
    decomposes: bool


def _by_case(observations: Sequence[RunObservation]) -> dict[str, list[RunObservation]]:
    buckets: dict[str, list[RunObservation]] = {}
    for one in observations:
        buckets.setdefault(one.case.base.id, []).append(one)
    return buckets


def metric_cells(name: str, metric: Metric,
                 observations: Sequence[RunObservation]) -> LineCells:
    """One metric over a population and over each of its cases.

    The whole-population call is the DEFINITION and is made even though the
    per-case calls could be summed: a metric that counts across case
    boundaries would otherwise be silently re-defined here as the sum of its
    parts, and the report and the comparison would print two different numbers
    under one name.
    """
    whole = metric(observations)
    per_case: dict[str, tuple[int, int]] = {}
    for case_id, rows in _by_case(observations).items():
        cell = metric(rows)
        per_case[case_id] = (cell.hits, cell.total)
    hits = sum(hits for hits, _total in per_case.values())
    total = sum(total for _hits, total in per_case.values())
    return LineCells(name=name, line=whole, per_case=per_case,
                     decomposes=(hits, total) == (whole.hits, whole.total))


def level_cells(side: RunSide, level: str, ids: set[str], control: bool) -> LineCells:
    """One v4 paired level as a Line: I≈C (or C′≈C) over the comparable triples.

    THE ARITHMETIC IS v4's, THE SHAPE IS OURS. `case_effects` already counts,
    per case, the repeats where the gateway arm agreed with the control (`ic`),
    where the control's twin did (`cc`) and how many triples were comparable at
    all (`n`); a Line of those sums is the agreement v4 prints, and it
    decomposes by construction. The control half is printed as its own line
    (`CONTROL_SUFFIX`) rather than folded in, because a move both arms made is
    the model's noise and not the gateway's work — the fact v4's paired effect
    subtracts inside one run and a reader of two runs has to see for himself.
    """
    per_case: dict[str, tuple[int, int]] = {}
    for case_id in sorted(ids):
        effect = side.levels[level].get(case_id)
        if effect is None:
            continue
        per_case[case_id] = (effect.cc if control else effect.ic, effect.n)
    hits = sum(hits for hits, _total in per_case.values())
    total = sum(total for _hits, total in per_case.values())
    name = level + CONTROL_SUFFIX if control else level
    return LineCells(name=name, line=Line(name, hits, total), per_case=per_case,
                     decomposes=True)


def cells_of(side: RunSide, ids: set[str], functions: MetricRegistry) -> dict[str, LineCells]:
    """Every comparable line of one run over the shared basis: the v5 metrics
    the caller allowed, then the six v4 levels with their control halves."""
    shared = [one for one in side.observations if one.case.base.id in ids]
    out: dict[str, LineCells] = {}
    for name in sorted(functions):
        out[name] = metric_cells(name, functions[name], shared)
    for level, _label in contracts.V4_LEVELS:
        out[level] = level_cells(side, level, ids, control=False)
        out[level + CONTROL_SUFFIX] = level_cells(side, level, ids, control=True)
    return out


# --- the difference, and what separates it from zero -------------------------------------

def paired_effects(a: LineCells, b: LineCells, clusters: dict[str, str]) -> list[stats.CaseEffect]:
    """The per-case difference of rates, as v4's own paired counter.

    `stats.CaseEffect` computes `(ic − cc)/n` and nothing else, so putting
    `ic = hits_B · total_A`, `cc = hits_A · total_B` and `n = total_A · total_B`
    makes that expression exactly `hits_B/total_B − hits_A/total_A` — the
    difference of the two runs' rates on this case, in integers and without a
    rounding step. The alternative was a second bootstrap over floats here, and
    a second bootstrap is a second definition of the interval the report
    already publishes.

    A case whose denominator is zero in EITHER run is left out: it has nothing
    to say about the difference, and counting it as a zero difference is the v4
    defect this benchmark exists to avoid — a pair with nothing to compare
    voting «they agree».
    """
    out: list[stats.CaseEffect] = []
    for case_id in sorted(set(a.per_case) & set(b.per_case)):
        a_hits, a_total = a.per_case[case_id]
        b_hits, b_total = b.per_case[case_id]
        if a_total == 0 or b_total == 0:
            continue
        cluster = clusters.get(case_id)
        if cluster is None:
            raise CompareError(f"{case_id}: случай есть в наблюдениях и нет в корпусе прогона — "
                               f"кластер для бутстрапа взять неоткуда")
        out.append(stats.CaseEffect(case_id=case_id, cluster=cluster,
                                    ic=b_hits * a_total, cc=a_hits * b_total,
                                    n=a_total * b_total))
    return out


@dataclass(frozen=True)
class LineDiff:
    """One line of A, the same line of B, and what separates them.

    `delta` is the POOLED difference of rates (B − A over the whole shared
    basis) and `effect` is the MEAN PER-CASE difference the interval is drawn
    around. They are printed as two numbers on purpose: they answer the same
    question weighted differently (by observations and by cases), and a tool
    that printed one of them under both names would be hiding which.

    `delta` is None when EITHER line has an empty denominator, and that is the
    whole reason it is optional. `Line.rate` is 0.0 on an empty line — it has
    to be, a rate needs a denominator — so subtracting the two rates of a line
    one run measured 12/12 and the other measured not at all prints «−100pp»,
    which reads as «B got worse» when the truth is «B measured nothing». A
    difference nobody can compute is «н/д», never a number.
    """

    name: str
    a: Line
    b: Line
    delta: float | None
    comparable: int
    cases: int
    effect: float
    low: float
    high: float
    verdict: str
    why: str


def difference(name: str, a: LineCells, b: LineCells, clusters: dict[str, str],
               reps: int, seed: int) -> LineDiff:
    """One line's difference, its cluster-bootstrap interval and its verdict.

    THE 1/n FLOOR IS APPLIED BEFORE THE VERDICT IS READ. A percentile bootstrap
    over cases that all moved the same way returns a zero-width interval, and a
    zero-width interval excludes zero however small the real difference is —
    the same trap `stats.tost_equivalence` widens against, in the other
    direction. The estimate cannot resolve finer than one case can move it.
    """
    pooled = None if (a.line.total == 0 or b.line.total == 0) else b.line.rate - a.line.rate
    cases = len(set(a.per_case) & set(b.per_case))
    if not (a.decomposes and b.decomposes):
        side = "A" if not a.decomposes else "B"
        return LineDiff(name=name, a=a.line, b=b.line, delta=pooled, comparable=0, cases=cases,
                        effect=0.0, low=0.0, high=0.0, verdict=NOTHING_TO_COMPARE,
                        why=f"строка не раскладывается по случаям в прогоне {side}: "
                            f"сумма по случаям не равна строке по всей популяции")
    effects = paired_effects(a, b, clusters)
    if not effects:
        return LineDiff(name=name, a=a.line, b=b.line, delta=pooled, comparable=0, cases=cases,
                        effect=0.0, low=0.0, high=0.0, verdict=NOTHING_TO_COMPARE,
                        why="ни одного случая с непустым знаменателем в обоих прогонах")
    interval = stats.cluster_bootstrap(effects, reps=reps, seed=seed)
    floor = 1.0 / len(effects)
    # Widened to the floor, then CLAMPED to the range a difference of two rates
    # can live in. The clamp cannot rescue a verdict — zero is inside [−1, +1],
    # so no bound crosses it by being clamped — and without it a line that lost
    # every case prints «[−116.67, −83.33]pp», a bound outside the parameter
    # space, which is the shape of a number a reader stops trusting.
    low = max(-1.0, min(interval.low, interval.point - floor))
    high = min(1.0, max(interval.high, interval.point + floor))
    verdict = SIGNIFICANT if (low > 0.0 or high < 0.0) else INDISTINGUISHABLE
    return LineDiff(name=name, a=a.line, b=b.line, delta=pooled, comparable=len(effects),
                    cases=cases, effect=interval.point, low=low, high=high,
                    verdict=verdict, why="")


# --- the case × line table (пункт 6) ------------------------------------------------------

@dataclass(frozen=True)
class CaseRow:
    """One cell of the «случай × строка» table: where a value changed, by how
    much, and enough about the case to know where to look."""

    case_id: str
    line: str
    family: str
    register: str
    a_hits: int
    a_total: int
    b_hits: int
    b_total: int
    change: float


def case_rows(a: dict[str, LineCells], b: dict[str, LineCells],
              cases: dict[str, Case]) -> list[CaseRow]:
    """Every (case, line) whose value MOVED, worst first.

    «Worst» is the most negative change — B scored lower than A — because the
    question this table answers is «кто именно ушёл в красное», and a table
    sorted by absolute size makes the reader find the regressions among the
    improvements. A cell whose denominator is zero on one side is NOT a change
    of value: it is a change of population, printed as such (`n/a`) and sorted
    last, so a case the run never reached cannot masquerade as a case the
    gateway broke.
    """
    rows: list[CaseRow] = []
    for name in sorted(set(a) & set(b)):
        a_cells, b_cells = a[name], b[name]
        for case_id in sorted(set(a_cells.per_case) & set(b_cells.per_case)):
            a_hits, a_total = a_cells.per_case[case_id]
            b_hits, b_total = b_cells.per_case[case_id]
            if (a_hits, a_total) == (b_hits, b_total):
                continue
            case = cases.get(case_id)
            if case is None:
                raise CompareError(f"{case_id}: случай есть в наблюдениях и нет в корпусе прогона")
            if a_total == 0 or b_total == 0:
                change = 0.0
            else:
                change = b_hits / b_total - a_hits / a_total
                if change == 0.0:
                    continue
            rows.append(CaseRow(case_id=case_id, line=name, family=case.kind,
                                register=case.register, a_hits=a_hits, a_total=a_total,
                                b_hits=b_hits, b_total=b_total, change=change))
    rows.sort(key=lambda row: (row.change, row.line, row.case_id))
    return rows


# --- the whole comparison ------------------------------------------------------------------

@dataclass(frozen=True)
class Comparison:
    """Everything the printed comparison is built from, computed once."""

    a: RunSide
    b: RunSide
    shared: tuple[str, ...]
    only_a: tuple[str, ...]
    only_b: tuple[str, ...]
    across_corpora: bool
    diffs: tuple[LineDiff, ...]
    refused: dict[str, str]
    rows: tuple[CaseRow, ...]
    reps: int
    seed: int


def compare(a: RunSide, b: RunSide, functions: MetricRegistry, refused: dict[str, str],
            across_corpora: bool, reps: int, seed: int) -> Comparison:
    """The comparison of two runs already read.

    `functions` and `refused` are PARAMETERS for the reason `report.assemble`
    takes a registry: the gate that decides what may be printed lives in
    `report.py`, this file obeys it, and a test has to be able to hand both a
    registry it controls and a refusal it invented — a tool that could only
    ever be driven by the real registry is a tool nobody has watched refuse.
    """
    if a.corpus_digest != b.corpus_digest and not across_corpora:
        raise CompareError(
            f"разные корпуса: A {a.corpus_digest[:12] or '—'} против "
            f"B {b.corpus_digest[:12] or '—'}; разница строк смешала бы смену корпуса "
            f"со сменой движка. Передайте --across-corpora, чтобы сравнить по общим id")
    ids_a, ids_b = case_ids(a), case_ids(b)
    shared = ids_a & ids_b
    # A metric named in `refused` is dropped HERE and not only by the caller
    # that built the registry. The gate's verdict is the instrument's law, and
    # a law enforced in one of two call sites is a law the second call site
    # breaks the day it is written — two tools printing different sets of
    # numbers about one run is how a reader ends up quoting the number that was
    # never allowed to print.
    allowed = {name: metric for name, metric in functions.items() if name not in refused}
    cells_a = cells_of(a, shared, allowed)
    cells_b = cells_of(b, shared, allowed)
    clusters = {case_id: case.cluster for case_id, case in a.cases.items()}
    diffs = tuple(difference(name, cells_a[name], cells_b[name], clusters, reps, seed)
                  for name in _printing_order(set(cells_a) & set(cells_b)))
    return Comparison(a=a, b=b, shared=tuple(sorted(shared)),
                      only_a=tuple(sorted(ids_a - ids_b)), only_b=tuple(sorted(ids_b - ids_a)),
                      across_corpora=across_corpora, diffs=diffs, refused=dict(refused),
                      rows=tuple(case_rows(cells_a, cells_b, a.cases)), reps=reps, seed=seed)


def _printing_order(names: set[str]) -> list[str]:
    """`contracts.METRIC_NAMES` first — the order the report prints — then the
    control halves of the levels beside their own level, then anything a caller
    registered under a name `contracts` does not declare, alphabetically.

    A line under an undeclared name is a finding and not a reason to print
    nothing: that is `report._printing_order`'s rule and this is the same rule
    over a set that also holds the `~контроль` halves."""
    out: list[str] = []
    for name in contracts.METRIC_NAMES:
        if name in names:
            out.append(name)
        control = name + CONTROL_SUFFIX
        if control in names:
            out.append(control)
    return out + sorted(names - set(out))


# --- rendering -----------------------------------------------------------------------------

def _meta_text(meta: dict[str, object], key: str) -> str:
    """One field of `<run>.meta.json` for the header, or «—».

    A missing field is PRINTED as «—» and never replaced by a plausible value:
    the header's job is to say what the two runs were, and «unknown» is one of
    the answers. Nothing here is a denominator, so an absent field costs a
    reader context and not a number."""
    value = meta.get(key)
    return "—" if value is None else str(value)


def header(comparison: Comparison) -> list[str]:
    a, b = comparison.a, comparison.b
    out = ["AgentPII-RU v5 — сравнение прогонов (разница = B − A)",
           f"  A {a.run_dir}  прогон {a.run_id} · ярус {_meta_text(a.meta, 'tier')} · "
           f"модель {_meta_text(a.meta, 'model')} · судья {_meta_text(a.meta, 'judge_model')} · "
           f"метка {_meta_text(a.meta, 'label')}",
           f"  B {b.run_dir}  прогон {b.run_id} · ярус {_meta_text(b.meta, 'tier')} · "
           f"модель {_meta_text(b.meta, 'model')} · судья {_meta_text(b.meta, 'judge_model')} · "
           f"метка {_meta_text(b.meta, 'label')}",
           f"  корпус A {a.corpus_digest[:12] or '—'} · корпус B {b.corpus_digest[:12] or '—'}"
           + ("  СРАВНЕНИЕ ПО ОБЩИМ id (--across-corpora): корпуса разные"
              if comparison.across_corpora and a.corpus_digest != b.corpus_digest else ""),
           f"  общая основа: {len(comparison.shared)} случаев из "
           f"{len(case_ids(a))} в A и {len(case_ids(b))} в B",
           f"  бутстрап: кластеры по общему значению, повторов {comparison.reps}, "
           f"сид {comparison.seed}; пол разрешения 1/n"]
    for label, only in (("только в A", comparison.only_a), ("только в B", comparison.only_b)):
        out.append(f"  {label}: {len(only)}" + (": " + " · ".join(only[:12])
                                                + (" …" if len(only) > 12 else "") if only else ""))
    if comparison.across_corpora and a.corpus_digest != b.corpus_digest:
        # WHOSE case is described in the tables. With one corpus the question
        # does not arise; across corpora the same id can carry a different
        # family, register and cluster on each side, and the bootstrap and the
        # case table both read A's. Said here rather than left to be inferred
        # from the code.
        out.append("  семья, регистр и кластер в таблицах — из корпуса A: при разных корпусах "
                   "один id может нести разные случаи, и сторона выбрана одна")
    for label, side in (("A", a), ("B", b)):
        if side.hopless or side.stopped:
            out.append(f"  {label}: наблюдений без хопов на диске {len(side.hopless)} · "
                       f"плечо не доиграло {len(side.stopped)}")
    return out


def render_diff(diff: LineDiff) -> str:
    """One line: A, B, the pooled difference, the paired effect with its
    interval, the verdict and how many cases said anything."""
    def cell(line: Line) -> str:
        if line.total == 0:
            return f"{'н/п':>7} {'':>8}"
        return f"{line.hits:>4}/{line.total:<6} {100 * line.rate:6.2f}%"

    delta = "     н/д" if diff.delta is None else f"{100 * diff.delta:+6.2f}pp"
    head = f"   {diff.name:24} A {cell(diff.a)}  B {cell(diff.b)}  Δ {delta}"
    if diff.verdict == NOTHING_TO_COMPARE:
        return f"{head}  {NOTHING_TO_COMPARE} — {diff.why}"
    return (f"{head}  парно {100 * diff.effect:+6.2f}pp "
            f"[{100 * diff.low:+6.2f}, {100 * diff.high:+6.2f}]  "
            f"{diff.verdict}{f' при n={diff.comparable}' if diff.verdict == INDISTINGUISHABLE else ''}"
            f"  сравнимо {diff.comparable}/{diff.cases}")


def render_rows(rows: Sequence[CaseRow], top: int) -> list[str]:
    out = ["", f"2. СЛУЧАЙ × СТРОКА — где значение изменилось, худшее первым "
               f"(показано {min(top, len(rows))} из {len(rows)})",
           "   случай            строка                 семья/регистр      A        B        изменение"]
    for row in rows[:top]:
        change = "n/a" if row.a_total == 0 or row.b_total == 0 else f"{100 * row.change:+7.2f}pp"
        out.append(f"   {row.case_id:17} {row.line:22} {row.family}/{row.register:10} "
                   f"{row.a_hits:>3}/{row.a_total:<4} {row.b_hits:>3}/{row.b_total:<4} {change:>10}")
    if not rows:
        out.append("   нет: ни одно значение не изменилось ни на одном случае")
    return out


def render(comparison: Comparison, cases_table: bool, top: int) -> list[str]:
    out = header(comparison)
    out += ["", "1. СТРОКИ — обе стороны и разница. «Δ» — разница долей по всей общей основе, "
                "«парно» — средняя разница ПО СЛУЧАЯМ, вокруг неё интервал."]
    out += [f"   «{NOTHING_TO_COMPARE}» и «{INDISTINGUISHABLE}» — разные вещи: "
            f"первое значит, что сравнивать было нечего, второе — что различие есть, "
            f"но такое n его не отделяет от нуля. «Δ н/д» — у одной из сторон пустой "
            f"знаменатель, и разницу долей считать не из чего.",
            "   «не отличимо от нуля» НЕ значит «одинаково»: это отсутствие доказательства "
            "различия, а не доказательство его отсутствия. Обратное доказывает TOST в отчёте прогона."]
    out += [render_diff(diff) for diff in comparison.diffs]
    if comparison.refused:
        out += ["", "   гейт отчёта не допустил к печати:"]
        out += [f"     {name}: {why}" for name, why in sorted(comparison.refused.items())]
    if cases_table:
        out += render_rows(comparison.rows, top)
    return out


def compare_dirs(a_dir: Path, b_dir: Path, across_corpora: bool, reps: int,
                 seed: int) -> Comparison:
    """The real registry, gated by the report's own gate: a metric the report
    refuses to print is not printed here either."""
    verdicts = report.gate_all(METRIC_FUNCTIONS)
    functions = {name: METRIC_FUNCTIONS[name] for name, verdict in verdicts.items()
                 if verdict.printable}
    refused = {name: verdict.why for name, verdict in verdicts.items() if not verdict.printable}
    return compare(read_side(a_dir), read_side(b_dir), functions, refused,
                   across_corpora, reps, seed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_a", type=Path, help="каталог прогона A")
    parser.add_argument("run_b", type=Path, help="каталог прогона B")
    parser.add_argument("--cases", action="store_true",
                        help="таблица «случай × строка»: где значение изменилось")
    parser.add_argument("--top", type=int, default=40, help="сколько строк таблицы печатать")
    parser.add_argument("--across-corpora", action="store_true",
                        help="сравнить прогоны на разных корпусах по пересечению id")
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS, help="тяг бутстрапа")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="сид бутстрапа")
    args = parser.parse_args()
    try:
        comparison = compare_dirs(args.run_a, args.run_b, args.across_corpora,
                                  args.reps, args.seed)
    # `report.ReportError` too, and not only ours: a directory with no
    # `<run>.hops.jsonl`, or one that is not a run at all, is refused by the
    # reader that owns that file, and a CLI that let that reach the user as a
    # traceback would be telling them their tool is broken when their
    # directory is.
    except (CompareError, report.ReportError) as error:
        print(f"сравнение отказано: {error}")
        return 2
    for line in render(comparison, args.cases, args.top):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
