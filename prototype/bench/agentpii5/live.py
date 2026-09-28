"""Real-time metrics dashboard for a RUNNING v5 run.

    python -m bench.agentpii5 live <run_dir>        # refresh every INTERVAL seconds
    python -m bench.agentpii5 live --latest         # newest run under bench/runs/
    python -m bench.agentpii5 live --once <run_dir> # one snapshot, no loop

No provider, engine, or judge is touched. This reads the run's files and
recomputes the SAME pure metrics the offline `hop-report` prints, on whatever
triples are on disk RIGHT NOW. It is a watch face, not a second estimator: the
numbers here converge to `hop-report`'s numbers as triples finish, and a
number that disagrees with the offline report at the end is a bug in this
module, not a new measurement.

WHY IT CAN READ A HALF-WRITTEN RUN. `drive_v5` writes every triple's rows
before the next one starts (`append_row` flushes each line). So at any instant
the on-disk `*.arms.jsonl`, `*.arms.v5.jsonl` and `*.hops.jsonl` hold exactly
the finished triples, and `report.observations_of` rebuilds the observations
from them without requiring the run's final `meta.json` or ledger.

Engine-free, like `compare`/`hop-report`: it imports `report` (file reader),
`metrics` (pure functions of observations), `actual_hops` and `causal_hops`
(pure), never `pseudex`/`licensing`.
"""

import argparse
import os
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from bench.agentpii5 import causal_hops, metrics, report
from bench.agentpii5.actual_hops import ActualAggregate, actual_events, aggregate
from bench.agentpii5.causal_hops import CausalAggregate, causal_events
from bench.agentpii5.hop_report import HISTORICAL_METRICS

# The four transitions the product cares about, in the order the owner reads
# them. `hop_owner` buckets are `IN/user`, `OUT/tool_arg`, `IN/tool`,
# `OUT/answer` plus the rarer `IN/document`, `OUT/summary`, `OUT/template` …
# which we still print — every bucket, never a hand-picked subset.
TRANSITION_ORDER: tuple[str, ...] = (
    "IN/user", "OUT/tool_arg", "IN/tool", "OUT/answer",
)


def _run_id_of(run_dir: Path) -> str:
    """The run id off ANY run file, so it works before the first triple writes
    `*.arms.jsonl`. `report.run_id_of` only globs arms; here the earliest file
    wins, so the watch face starts rendering from the very first second."""
    for suffix in (".spend.tsv", ".meta.json", ".arms.v5.jsonl", ".hops.jsonl", ".arms.jsonl"):
        found = sorted(run_dir.glob(f"*{suffix}"))
        if found:
            return found[0].name[: -len(suffix)]
    raise report.ReportError(f"{run_dir}: no run file yet — not a run directory")


def _rate(hits: int, total: int) -> str:
    if not total:
        return "н/п"
    return f"{hits}/{total} ({100 * hits / total:.2f}%)"


def live_snapshot(run_dir: Path) -> dict[str, object]:
    """One snapshot of the run as it stands right now.

    Returns a JSON-safe dict. `state` is one of ``starting`` (no triple has
    finished), ``no_corpus`` (directory not a run yet) or ``live`` (at least
    one observation is readable)."""
    run_dir = run_dir.resolve()
    base: dict[str, object] = {"run_dir": str(run_dir), "ts": datetime.now().isoformat(timespec="seconds")}

    if not run_dir.is_dir():
        return {**base, "state": "missing"}
    if not (run_dir / "corpus.v5.json").exists():
        return {**base, "state": "no_corpus"}

    try:
        cases = report.v5_cases(run_dir)
    except report.ReportError as error:
        return {**base, "state": "no_corpus", "error": str(error)}

    try:
        half = report.observations_of(run_dir, (), cases)
    except report.ReportError:
        # No `*.arms.jsonl` yet: zero finished triples, still a valid state.
        return {**base, "state": "starting", "done": 0, "corpus": len(cases)}

    observations = half.observations
    historical: dict[str, dict[str, int]] = {}
    for name in HISTORICAL_METRICS:
        line = metrics.METRIC_FUNCTIONS[name](observations)
        historical[name] = {"hits": line.hits, "total": line.total}

    actual: ActualAggregate = aggregate(
        tuple(actual_events(one.case, one.run) for one in observations))
    causal: CausalAggregate = causal_hops.aggregate(
        tuple(causal_events(one.case, one.run) for one in observations))
    # Render the causal table HERE, where the real dataclasses exist; the JSON
    # snapshot only carries the rendered lines (and the numeric `asdict`) so the
    # viewer never rebuilds nested `CausalLine`s from a dict.
    causal_render: list[str] = list(causal_hops.render(causal))

    # The hop-owner breakdown = the four transitions, plus every rarer bucket.
    owners: dict[str, dict[str, dict[str, int]]] = {}
    buckets = metrics.by_axis(observations, "hop_owner")
    for owner in sorted(buckets):
        rows = buckets[owner]
        owners[owner] = {
            name: {"hits": metrics.METRIC_FUNCTIONS[name](rows).hits,
                   "total": metrics.METRIC_FUNCTIONS[name](rows).total}
            for name in metrics.HOP_SLICEABLE
        }

    return {
        **base,
        "state": "live",
        "done": len(observations),
        "hopless": len(half.hopless),
        "stopped": len(half.stopped),
        "corpus": len(cases),
        "historical": historical,
        "owners": owners,
        "actual": asdict(actual),
        "causal": asdict(causal),
        "causal_render": causal_render,
    }


def _historical_table(snapshot: dict[str, object]) -> list[str]:
    rows = ["## Historical (completed-only, все 13 метрик спринта)", "",
            "| Metric | Hits/total |", "|---|---:|"]
    hist = snapshot["historical"]
    assert isinstance(hist, dict)
    for name in HISTORICAL_METRICS:
        line = hist[name]
        assert isinstance(line, dict)
        rows.append(f"| {name} | {_rate(int(line['hits']), int(line['total']))} |")
    return rows


def _owners_table(snapshot: dict[str, object]) -> list[str]:
    owners = snapshot.get("owners") or {}
    assert isinstance(owners, dict)
    if not owners:
        return []
    columns = tuple(metrics.HOP_SLICEABLE)
    header = ["## Переходы (по hop_owner)", "",
              "| owner | " + " | ".join(columns) + " |",
              "|---|" + "---:|" * len(columns)]
    rows = list(header)
    order = tuple(o for o in TRANSITION_ORDER if o in owners) + tuple(
        o for o in sorted(owners) if o not in TRANSITION_ORDER)
    for owner in order:
        cells = [_rate(int(owners[owner][c]["hits"]), int(owners[owner][c]["total"]))
                 for c in columns]
        rows.append(f"| {owner} | " + " | ".join(cells) + " |")
    return rows


def _actual_table(snapshot: dict[str, object]) -> list[str]:
    actual = snapshot.get("actual")
    if not actual:
        return []
    assert isinstance(actual, dict)
    overall = actual.get("overall") or {}
    by_type = actual.get("by_type") or []
    rows = ["", "## Actual OUT (листовые события, M0 estimator)", "",
            f"Листовых событий: {actual.get('events_total')}; "
            f"не применимо: {actual.get('not_applicable')}; "
            f"прогонов: {actual.get('runs')}.",
            "",
            "| Type | Cand. | Attr. | Value | Form | Form∅ | Residual | Joint |",
            "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for item in (overall, *by_type):
        count = int(item.get("candidates") or 0)
        rows.append(
            f"| {item.get('pii_type') or 'untyped'} | {count} | "
            + " | ".join(_rate(int(item.get(k) or 0), count) for k in
                         ("attributed", "value_ok", "form_ok", "form_unmeasured",
                          "residual", "joint_ok"))
            + " |")
    return rows


def render(snapshot: dict[str, object]) -> str:
    state = snapshot.get("state")
    if state != "live":
        head = snapshot.get("run_dir") or "?"
        return "\n".join([
            "=== pseudex v5 LIVE ===",
            f"run_dir: {head}",
            f"state: {state}" + (f" ({snapshot.get('error')})" if snapshot.get("error") else ""),
            "ждём завершения первой тройки / создания каталога прогона…",
        ])

    blocks: list[str] = []
    blocks.append("=== pseudex v5 LIVE ===")
    blocks.append(
        f"готово: {snapshot.get('done')} · корпус: {snapshot.get('corpus')} · "
        f"hopless: {snapshot.get('hopless')} · stopped: {snapshot.get('stopped')} · "
        f"обновлено {snapshot.get('ts')}")
    blocks.append("")
    blocks.extend(_historical_table(snapshot))
    blocks.extend(_owners_table(snapshot))
    blocks.extend(_actual_table(snapshot))

    causal_render = snapshot.get("causal_render")
    if causal_render:
        blocks.extend(["", "## Actual causal (recorded chronology, M03 estimator)", ""])
        blocks.extend(str(line) for line in causal_render)
    return "\n".join(blocks)


def _newest_run(runs_root: Path) -> Path | None:
    if not runs_root.is_dir():
        return None
    candidates = [p for p in runs_root.rglob("corpus.v5.json")]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime).parent


def _clear() -> None:
    if os.environ.get("TERM") and os.environ.get("TERM") != "dumb" and not os.environ.get("NO_COLOR"):
        print("\033[2J\033[H", end="")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", nargs="?", type=Path,
                        help="каталог прогона (тот, что печатает `run`)")
    parser.add_argument("--latest", action="store_true",
                        help="самый свежий прогон под bench/runs/")
    parser.add_argument("--once", action="store_true",
                        help="один снимок, без цикла")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="секунды между обновлениями (по умолчанию 2)")
    args = parser.parse_args()

    run_dir: Path
    if args.latest:
        here = Path(__file__).resolve().parent
        newest = _newest_run(here.parent / "runs")
        if newest is None:
            print("нет ни одного каталога прогона под bench/runs/", file=__import__("sys").stderr)
            return 2
        run_dir = newest
    elif args.run_dir is not None:
        run_dir = args.run_dir
    else:
        parser.error("нужен <run_dir> или --latest")

    if args.once:
        print(render(live_snapshot(run_dir)))
        return 0

    interval = max(0.5, args.interval)
    last: str = ""
    while True:
        snapshot = live_snapshot(run_dir)
        text = render(snapshot)
        if text != last:
            _clear()
            print(text, flush=True)
            last = text
        time.sleep(interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
