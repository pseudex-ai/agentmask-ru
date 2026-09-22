"""AgentPII-RU v5 — one row per run, so a regression between versions is
visible without opening a folder (ТЗ `docs/tz-bench-harness.md` §5.2, item 16).

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.trend                     # markdown
    python3 -m bench.agentpii5.trend --json              # the same rows as data
    python3 -m bench.agentpii5.trend --tier medium --lines leak,round_trip

TWO SOURCES AND NEITHER IS THE TEXT REPORT. The registry (`runs.json`, §1.2,
read through `runinfo`) says what a run WAS — date, tier, label, models,
digests, what it cost, whether it finished; the run's own `<run>.report.json`
(§5.1) says what it MEASURED. A trend that parsed `<run>.report.txt` broke the
day a column moved by one space, which is the whole reason §5.1 exists.

THE REGISTRY IS READ THROUGH `runinfo`, NEVER RE-PARSED HERE. `RunRecord` and
`read_runs` are that module's, and a second reader of one file is a second
opinion about what a run was: the day a field is renamed, one of the two would
print an empty column instead of going red. This module owns the JOIN and the
table, nothing else.

A RUN WITH NO REPORT IS A ROW, NOT A GAP. An interrupted run, or one whose
report was never built, prints «отчёта нет» in the cells it cannot fill and
keeps its registry fields. Dropping it would make the trend a list of the runs
that went well, and the run that stopped at case 40 is exactly the one a reader
is looking for a month later.
"""
import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from bench.agentpii5.reportjson import read as read_report
from bench.agentpii5.runinfo import RUNS_PATH
from bench.agentpii5.runinfo import RunInfoError, RunRecord, read_runs

HERE: Path = Path(__file__).resolve().parent

# THE LINES A TREND IS READ FOR. Not every metric: thirty columns is a table
# nobody scans, and the regression a reader is looking for is in the promise the
# product makes — nothing of the customer's reached the model (`leak`,
# `coverage`), the real value reached the tool (`round_trip`, `end_to_end`),
# nothing of ours was left behind (`residual`), the form survived both ways
# (`form_hIN`, `form_hOUT`), the answer carried the truth (`answer_real`), and
# ordinary text was left alone (`overmask`). `--lines` overrides for a run that
# is being read for something else.
TREND_LINES: tuple[str, ...] = (
    "leak", "coverage", "round_trip", "end_to_end", "overmask", "residual",
    "form_hIN", "form_hOUT", "answer_real")
NO_REPORT: str = "отчёта нет"
# How much a line must fall between two consecutive runs of one tier before the
# trend points at the pair. One point, because that is roughly the width of the
# interval a `medium` run resolves — below it `compare` would say «различие не
# отличимо от нуля» and the arrow would be noise.
DEFAULT_REGRESSION_PP: float = 1.0


@dataclass(frozen=True)
class TrendRow:
    """One registry row joined to its report. `lines` is empty and `problem`
    says why when the report could not be read — the row still prints."""

    record: RunRecord
    lines: dict[str, tuple[int, int]]
    incomplete: bool | None
    problem: str


def ordered(records: Sequence[RunRecord]) -> tuple[RunRecord, ...]:
    """Oldest first, by the moment the run STARTED.

    By `started` and not by `finished`: a run that took four hours finished
    after one begun later, and a trend ordered by the end would swap the pair
    whose difference it exists to show. The run id breaks a tie, so two runs
    begun in the same second still order the same way on every machine."""
    return tuple(sorted(records, key=lambda one: (one.started, one.run_id)))


def trend_rows(registry: Sequence[RunRecord], names: Sequence[str]) -> tuple[TrendRow, ...]:
    """Every registry row with the lines its report carries.

    The report is read through `reportjson.read`, so the trend and the report
    agree by construction; a row whose report is missing or unreadable carries
    the reason and keeps its registry fields."""
    out: list[TrendRow] = []
    for record in ordered(registry):
        try:
            document = read_report(Path(record.run_dir))
        except (ValueError, OSError) as broken:
            out.append(TrendRow(record=record, lines={}, incomplete=None,
                                problem=f"{NO_REPORT}: {broken}"))
            continue
        found = document.get("lines")
        rows = found if isinstance(found, dict) else {}
        lines: dict[str, tuple[int, int]] = {}
        for name in names:
            row = rows.get(name)
            if isinstance(row, dict):
                lines[name] = (int(row.get("hits", 0)), int(row.get("total", 0)))
        out.append(TrendRow(record=record, lines=lines,
                            incomplete=bool(document.get("incomplete")), problem=""))
    return tuple(out)


def _cell(row: TrendRow, name: str) -> str:
    pair = row.lines.get(name)
    if pair is None:
        return "—"
    hits, total = pair
    # «0/0» rather than «0.0%»: a line with an empty population said nothing,
    # and printing it as a zero rate is the one reading that turns silence into
    # a failure.
    return "0/0" if not total else f"{100 * hits / total:.1f}%"


def _verdict(row: TrendRow) -> str:
    """What the run ended as, in one cell: the registry's verdict, the report's
    «НЕПОЛНЫЙ» mark, the state when it was interrupted, and the count §1.4
    records of cases a provider outage took."""
    if row.problem:
        return row.problem
    parts = [row.record.verdict]
    if row.record.state != "finished":
        parts.append(row.record.state)
    if row.record.transport_terminated:
        parts.append(f"обрыв {row.record.transport_terminated}")
    if row.incomplete:
        parts.append("⚠")
    return " · ".join(parts)


def render_markdown(rows: Sequence[TrendRow], names: Sequence[str]) -> list[str]:
    """One table, oldest first, so the eye reads down the way time runs.

    The label is a column and not a footnote: §1.3 made it mandatory above
    `nano` precisely because «прогон от 23.09» means nothing a month later, and
    a trend that hid it would undo that."""
    head = ["дата", "ярус", "метка", "случаев", "K", "$", "вердикт"] + list(names)
    out = ["| " + " | ".join(head) + " |",
           "|" + "|".join("---" for _one in head) + "|"]
    for row in rows:
        cells = [row.record.started[:10], row.record.tier, row.record.label or "—",
                 str(row.record.cases), str(row.record.repeats),
                 f"{row.record.spent_usd:.2f}", _verdict(row)]
        out.append("| " + " | ".join(cells + [_cell(row, name) for name in names]) + " |")
    return out


def render_json(rows: Sequence[TrendRow], names: Sequence[str]) -> dict[str, object]:
    """The same rows as data — what an article's table and a CI check read."""
    return {
        "lines": list(names),
        "runs": [{
            "run_id": row.record.run_id, "benchmark": row.record.benchmark,
            "started": row.record.started, "finished": row.record.finished,
            "state": row.record.state, "tier": row.record.tier, "label": row.record.label,
            "note": row.record.note, "cases": row.record.cases, "repeats": row.record.repeats,
            "triples_done": row.record.triples_done,
            "transport_terminated": row.record.transport_terminated,
            "model": row.record.model, "judge_model": row.record.judge_model,
            "corpus_digest": row.record.corpus_digest,
            "ladder_digest": row.record.ladder_digest,
            "spent_usd": row.record.spent_usd, "ceiling_usd": row.record.ceiling_usd,
            "wall_s": row.record.wall_s, "verdict": row.record.verdict,
            "worktree": row.record.worktree, "run_dir": row.record.run_dir,
            "incomplete": row.incomplete, "problem": row.problem or None,
            "lines": {name: {"hits": hits, "total": total,
                             "rate": (hits / total) if total else None}
                      for name, (hits, total) in sorted(row.lines.items())}}
            for row in rows]}


def regressions(rows: Sequence[TrendRow], names: Sequence[str],
                points: float) -> list[str]:
    """Where a line fell between two CONSECUTIVE runs of the same tier, by more
    than `points` percentage points.

    THE SAME TIER, ALWAYS. A `nano` run beside a `medium` one differ by three
    orders of magnitude in n, and calling that difference a regression would
    make the trend fire on every cheap smoke run. Comparing runs is `compare`'s
    job and it does it with an interval; this is the eye-catcher that says which
    pair is worth asking `compare` about."""
    out: list[str] = []
    for tier in sorted({row.record.tier for row in rows}):
        of_tier = [row for row in rows if row.record.tier == tier]
        for earlier, later in zip(of_tier, of_tier[1:]):
            for name in names:
                before, after = earlier.lines.get(name), later.lines.get(name)
                if before is None or after is None or not before[1] or not after[1]:
                    continue
                drop = 100 * (before[0] / before[1] - after[0] / after[1])
                if drop > points:
                    out.append(f"{tier} · {name}: {earlier.record.started[:10]} "
                               f"{100 * before[0] / before[1]:.1f}% → "
                               f"{later.record.started[:10]} "
                               f"{100 * after[0] / after[1]:.1f}%  (−{drop:.1f}pp) · "
                               f"{earlier.record.run_id[:8]} → {later.record.run_id[:8]}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", default=str(RUNS_PATH), help="реестр прогонов")
    parser.add_argument("--tier", default="", help="только этот ярус")
    parser.add_argument("--benchmark", default="", help="только этот бенчмарк")
    parser.add_argument("--lines", default=",".join(TREND_LINES),
                        help="какие строки метрик в колонках")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--regression-pp", type=float, default=DEFAULT_REGRESSION_PP)
    args = parser.parse_args()
    names = [one.strip() for one in args.lines.split(",") if one.strip()]
    registry_path = Path(args.runs)
    # `runinfo.read_runs` reads a missing registry as an empty one — the first
    # run writes a file that does not exist yet — so the DISTINCTION is printed
    # here rather than made into a second reader: «реестра нет» and «прогонов
    # нет» are different facts, and a table that showed neither would say the
    # benchmark had never been run.
    if not registry_path.exists():
        print(f"{registry_path} нет: реестр создаёт первый прогон (ТЗ §1.2)", file=sys.stderr)
        return 2
    try:
        registry = read_runs(registry_path)
    except RunInfoError as broken:
        print(broken, file=sys.stderr)
        return 2
    if args.tier:
        registry = tuple(one for one in registry if one.tier == args.tier)
    if args.benchmark:
        registry = tuple(one for one in registry if one.benchmark == args.benchmark)
    rows = trend_rows(registry, names)
    if args.json:
        print(json.dumps(render_json(rows, names), ensure_ascii=False, indent=2,
                         sort_keys=True))
        return 0
    for line in render_markdown(rows, names):
        print(line)
    fallen = regressions(rows, names, args.regression_pp)
    print("\nрегресс между соседними прогонами одного яруса "
          f"(> {args.regression_pp:.1f}pp):")
    for line in fallen or ["нет"]:
        print(f"  {line}")
    # A trend that could not read a report says so in its exit code: a CI step
    # that only looked at stdout would go green on a table full of «отчёта нет».
    return 1 if any(row.problem for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
