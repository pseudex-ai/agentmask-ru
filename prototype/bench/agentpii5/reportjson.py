"""AgentPII-RU v5 — the report as DATA, and the public substring of it
(ТЗ `docs/tz-bench-harness.md` §5.1 and §5.3, items 15 and 17).

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.reportjson <v5 run dir> <v4 run dir>
    python3 -m bench.agentpii5.reportjson <v5 run dir> <v4 run dir> --public

WHY A SECOND FILE BESIDE `<run>.report.txt`. The text report is written for a
person and is the right shape for one: v4's own block verbatim, seven numbered
sections, examples. Everything built ON a run — the trend (§5.2), an article, a
diff of two runs — has been re-parsing that text, and a line whose spacing
changed took the trend with it. So the same `SideBySide` is written a second
time as one versioned schema, and every consumer reads THAT.

IT IS THE SAME OBJECT, NOT A SECOND DERIVATION. `build` takes the `ReportParts`
and the `SideBySide` that `report.py` assembled and re-shapes them; it computes
no rate, no interval and no verdict of its own. The one thing it adds is the
cost block, and even there the three atoms (`report._triple_cost`,
`report._judge_spend`, `report._ledger_total`) are the functions the text lines
are built from — so the text and the JSON can disagree about layout and never
about a number.

THE PUBLIC FILE IS BUILT BY AN ALLOWLIST, NEVER BY DELETION (§5.3). `public`
SELECTS the keys of `PUBLIC_TOP_LEVEL` out of the full document and the lines of
`PUBLIC_LINES` out of its lines. A field added to the private report tomorrow is
therefore absent from the public one until somebody names it — which is the
opposite of «всё кроме», where a new private field is published by default and
nobody finds out. `test_reportjson` plants a field and demands its absence.

NO VALUE FROM THE CORPUS IS IN EITHER FILE, and the private one carries case
IDs only where the text report already prints them (the excluded observations).
The public one carries no id at all: a case id is not personal data, but a
public file that named cases would let a reader of the article ask for them.
"""
import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bench.agentpii5 import contracts, records
from bench.agentpii5.contracts import Line, Metric, MetricSpec, SideBySide
from bench.agentpii5.metrics import METRIC_FUNCTIONS
from bench.agentpii5.report import (
    ReportError,
    ReportParts,
    _holes,
    _judge_spend,
    _ledger_total,
    _stopped,
    _triple_cost,
    assemble,
    meta_of,
    read_parts,
    run_id_of,
)

# The schema every consumer pins. Bumped only when a field CHANGES MEANING;
# adding a field is not a bump, because a reader that ignores unknown keys goes
# on working — and a version that moved for every addition would be a version
# nobody could use to decide whether to re-read the file.
REPORT_JSON_VERSION: int = 1

# The two file names, now ROWS OF `contracts.RUN_FILES`, so `records.run_file`
# builds both paths the way it builds every other run file. This module shipped
# with a local path helper while the rows did not exist yet; it is gone, because
# two ways to spell a run file is one rename away from a reader looking for a
# file no run writes (`report.meta_of` says the same about `meta.json`).
REPORT_JSON_NAME: str = "<run>.report.json"
PUBLIC_JSON_NAME: str = "<run>.public.json"


# --- §5.3 the allowlist -------------------------------------------------------------------

# WHAT MAY BE SHOWN OUTSIDE, SPELLED OUT. Every key not here stays private,
# including one added to the private document after this line was written.
PUBLIC_TOP_LEVEL: tuple[str, ...] = (
    "schema", "benchmark", "generated_at", "tier", "cases", "repeats",
    "corpus_digest", "incomplete", "incomplete_reasons", "lines")
PUBLIC_LINE_FIELDS: tuple[str, ...] = (
    "name", "hits", "total", "rate", "ci_low", "ci_high", "certified")
# THE LINES ARE THE CONTRACT'S `public` FAMILY MINUS ITS DIAGNOSTICS, and the
# subtraction is the point. `rewrite_ratio_v5` and `shared_block_answer` are in
# the `public` family and their own declarations say they are NOT the public
# quantities of that name — a reader outside would take «rewrite_ratio» for the
# public harness's per-message ratio, which is a different number over a
# different population. A line that would be misread outside is worse than a
# line that is missing.
PUBLIC_LINES: tuple[str, ...] = tuple(
    name for name in contracts.PUBLIC_METRIC_NAMES
    if name not in contracts.DIAGNOSTIC_METRIC_NAMES)
SPEC_BY_NAME: dict[str, MetricSpec] = {spec.name: spec for spec in contracts.METRICS}


# --- the document -------------------------------------------------------------------------

def line_json(line: Line) -> dict[str, object]:
    """One `Line` as data: the counters, the rate, the exact interval and what a
    flawless line certifies.

    THE COUNTERS ARE THE RECORD AND THE RATE IS A CONVENIENCE. `Line` stores
    hits and total and derives the rest for the same reason (§5 of
    `contracts.py`), so a consumer that wants to re-aggregate can, and one that
    only prints a percentage does not have to divide."""
    low, high = line.interval
    spec = SPEC_BY_NAME.get(line.name)
    return {"name": line.name, "hits": line.hits, "total": line.total, "rate": line.rate,
            "ci_low": low, "ci_high": high, "certified": line.certified,
            "family": spec.family if spec is not None else None,
            "scope": spec.scope if spec is not None else None,
            "diagnostic": spec.diagnostic if spec is not None else None}


def cost_json(run_dir: Path) -> dict[str, object]:
    """What the run cost, from the same three atoms the text lines are built
    from (`report.cost_lines`). A missing file leaves the field `null` and says
    which one — «$0.00» on a run whose triples file was never copied reads as a
    free run, and in JSON nobody would even see the difference."""
    run_id = run_id_of(run_dir)
    triples_path = records.run_file(run_dir, run_id, "<run>.triples.jsonl")
    meta = meta_of(run_dir, run_id)
    ceiling = meta.get("ceiling_usd")
    ledger = _ledger_total(records.run_file(run_dir, run_id, "<run>.spend.tsv"))
    if not triples_path.exists():
        return {"triples_usd": None, "judge_usd": None, "ledger_usd": ledger,
                "ceiling_usd": ceiling if isinstance(ceiling, (int, float)) else None,
                "triples": None, "missing": triples_path.name}
    triples = records.read_rows(triples_path)
    spent = sum(_triple_cost(one, triples_path) for one in triples)
    judge = sum(_judge_spend(one, triples_path) for one in triples)
    return {
        "triples_usd": round(spent, 6), "judge_usd": round(judge, 6), "ledger_usd": ledger,
        "ceiling_usd": ceiling if isinstance(ceiling, (int, float)) else None,
        "triples": {
            "complete": sum(1 for one in triples if one.get("status") == "complete"),
            "excluded": sum(1 for one in triples if one.get("status") == "excluded"),
            "refused": sum(1 for one in triples if one.get("status") == "refused"),
            "all": len(triples)},
        "missing": None}


def judge_json(side: SideBySide, parts: ReportParts) -> dict[str, object]:
    """The judge half, with the RECOMPUTED calibration flag — the same one the
    header prints. A stamp that claimed `calibrated` while its own numbers
    refuse it printed «откалиброван» once (finding #7); a JSON that carried the
    file's flag would put that back for every machine reader."""
    stamp = side.judge
    return {"model": stamp.judge_model, "prompt_sha256": stamp.prompt_sha256, "n": stamp.n,
            "raw_agreement": stamp.raw_agreement, "kappa": stamp.kappa,
            "per_type_kappa": dict(stamp.per_type_kappa),
            "repeat_disagreement": stamp.repeat_disagreement, "calibrated": stamp.calibrated,
            "problems": list(parts.judge.problems), "labels": dict(side.judge_labels),
            "pregate": side.judge_pregate}


def incomplete_reasons(side: SideBySide, parts: ReportParts) -> tuple[str, ...]:
    """Why the header carries «НЕПОЛНЫЙ», as a list a machine can branch on.

    The text report prints the three causes in three different sections; a
    consumer that had to tell them apart was reading three places and guessing.
    The causes themselves are `report.assemble`'s, read back off the assembled
    object rather than recomputed."""
    out: list[str] = []
    blocked = sorted(name for name in side.v5_refused
                     if name not in contracts.DIAGNOSTIC_METRIC_NAMES)
    if blocked:
        out.append("гейт отказал непечатаемым метрикам: " + ", ".join(blocked))
    if parts.judge.problems:
        out.append("судья не откалиброван: " + " · ".join(parts.judge.problems))
    holes = _holes(side.excluded_observations)
    if holes:
        out.append(f"наблюдений без хопов: {len(holes)}")
    return tuple(out)


def build(parts: ReportParts, side: SideBySide) -> dict[str, object]:
    """The whole §5.1 document from a report that has already been assembled.

    Takes the two objects instead of two directories so `report_lines` and this
    can be produced from ONE assembly: a second `assemble` over the same files
    would be a second measurement, and the day one of them read a file the other
    did not, the markdown and the JSON beside it would disagree."""
    run_dir = parts.v5_dir
    run_id = run_id_of(run_dir)
    meta = meta_of(run_dir, run_id)
    reasons = incomplete_reasons(side, parts)
    return {
        "schema": REPORT_JSON_VERSION,
        "benchmark": contracts.BENCHMARK,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "baseline_dir": str(parts.v4_dir),
        "tier": meta.get("tier"),
        "repeats": meta.get("repeats"),
        # TWO COUNTS, BECAUSE K REPEATS MAKE THEM DIFFERENT. A run of 100 cases
        # at K=3 has 300 observations, and a trend row that printed one of them
        # under the other's name would show a run tripling in size when only the
        # repeats moved.
        "cases": len({one.case.base.id for one in parts.half.observations}),
        "observations": len(parts.half.observations),
        "corpus_digest": side.corpus_digest_v5 or None,
        "corpus_digest_baseline": side.corpus_digest_v4 or None,
        "models": {"agent": meta.get("model") or side.agent_model,
                   "judge": meta.get("judge_model") or None},
        # Written by the provider layer when a run goes through it (item 12);
        # `null` on a run that predates it, never an invented price.
        "provider": meta.get("provider"),
        "gateway": meta.get("gateway"),
        "label": meta.get("label"),
        "note": meta.get("note"),
        "prompt_sha256": meta.get("prompt_sha256"),
        "incomplete": side.incomplete,
        "incomplete_reasons": list(reasons),
        "cost": cost_json(run_dir),
        "judge": judge_json(side, parts),
        "lines": {name: line_json(line) for name, line in sorted(side.v5_lines.items())},
        "slices": {name: {axis: {bucket: line_json(line) for bucket, line in sorted(cells.items())}
                          for axis, cells in sorted(axes.items())}
                   for name, axes in sorted(side.v5_by_axis.items())},
        "v4_levels": [{
            "level": row.level, "label": row.label, "comparable": row.comparable,
            "triples": row.triples, "agree_ic": row.agree_ic, "agree_cc": row.agree_cc,
            "effect": row.effect, "ci_low": row.ci_low, "ci_high": row.ci_high,
            "tost_verdict": row.tost_verdict, "tost_low": row.tost_low,
            "tost_high": row.tost_high, "mcnemar_p": row.mcnemar_p,
            "discordant_b": row.discordant_b, "discordant_c": row.discordant_c,
            "icc_case": row.icc_case, "icc_value": row.icc_value, "deff": row.deff}
            for row in side.v4_levels],
        "refused": dict(sorted(side.v5_refused.items())),
        "excluded_observations": {
            "holes": list(_holes(side.excluded_observations)),
            "stopped": list(_stopped(side.excluded_observations))},
    }


def public(full: Mapping[str, object]) -> dict[str, object]:
    """The §5.3 substring: the allowlisted keys of `full`, and only the
    allowlisted lines inside them.

    SELECTION, never deletion. `{key: full[key] for key in PUBLIC_TOP_LEVEL}` is
    the whole rule, and a private field invented tomorrow is outside it by
    construction. The other spelling — copy and pop the secrets — publishes
    every new field by default and is discovered by a reader of the article."""
    out: dict[str, object] = {}
    for key in PUBLIC_TOP_LEVEL:
        if key not in full:
            raise ReportError(f"публичный отчёт: в приватном нет поля {key!r} "
                              f"(есть {sorted(full)}) — список в контракте и документ разошлись")
        out[key] = full[key]
    lines = full.get("lines")
    if not isinstance(lines, dict):
        raise ReportError(f"публичный отчёт: lines не объект, а {type(lines).__name__}")
    out["lines"] = {
        name: {field: value for field, value in dict(row).items() if field in PUBLIC_LINE_FIELDS}
        for name, row in sorted(lines.items()) if name in PUBLIC_LINES and isinstance(row, dict)}
    # The names the public file leaves out, COUNTED. A public report that
    # silently held five lines out of thirty would read as a benchmark with five
    # lines; the count says «this is a substring» without naming what is in the
    # rest.
    out["lines_withheld"] = len(lines) - len(out["lines"])
    return out


@dataclass(frozen=True)
class Written:
    """What `write` produced, so a caller can print both paths without guessing
    how they are spelled."""

    report: Path
    public: Path
    document: dict[str, object]


def write(v5_run_dir: Path, v4_run_dir: Path, functions: dict[str, Metric]) -> Written:
    """`<run>.report.json` and `<run>.public.json`, from ONE assembly.

    `functions` is a parameter for the reason `report.assemble` takes one: the
    gate's own test registers a deliberately broken metric under a real name and
    watches the document mark itself incomplete. A writer that could only ever
    be built from the real registry is a writer nobody has seen refuse."""
    parts = read_parts(v5_run_dir, v4_run_dir)
    side = assemble(parts, functions)
    document = build(parts, side)
    run_id = run_id_of(v5_run_dir)
    report_path = records.run_file(v5_run_dir, run_id, REPORT_JSON_NAME)
    public_path = records.run_file(v5_run_dir, run_id, PUBLIC_JSON_NAME)
    report_path.write_text(json.dumps(document, ensure_ascii=False, indent=2,
                                      sort_keys=True) + "\n", encoding="utf-8")
    public_path.write_text(json.dumps(public(document), ensure_ascii=False, indent=2,
                                      sort_keys=True) + "\n", encoding="utf-8")
    return Written(report=report_path, public=public_path, document=document)


def write_side_by_side(v5_run_dir: Path, v4_run_dir: Path) -> Written:
    """The two JSON files of a REAL run: the real metric registry, no seam.

    The twin of `report.render_side_by_side`, and it exists for the same reason:
    a caller that finishes a run must not be the place that decides which
    metrics are in force, or a run's text report and its JSON could be built
    from two registries."""
    return write(v5_run_dir, v4_run_dir, METRIC_FUNCTIONS)


def read(run_dir: Path) -> dict[str, object]:
    """A run's `<run>.report.json`, for `trend` and `compare`. A missing file is
    a refusal naming it: «нет отчёта» and «отчёт пуст» are different facts about
    a run, and the trend must be able to print the first."""
    path = records.run_file(run_dir, run_id_of(run_dir), REPORT_JSON_NAME)
    if not path.exists():
        raise ReportError(f"{path} нет: соберите отчёт "
                          f"(python3 -m bench.agentpii5.reportjson {run_dir} <base>)")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ReportError(f"{path}: ожидался объект, а не {type(raw).__name__}")
    return {str(key): value for key, value in raw.items()}


def summary_lines(document: Mapping[str, object], names: Sequence[str]) -> list[str]:
    """The named lines of one document as «name hits/total rate» — what `trend`
    prints per run and what a human checks a JSON against."""
    lines = document.get("lines")
    rows = lines if isinstance(lines, dict) else {}
    out: list[str] = []
    for name in names:
        row = rows.get(name)
        if not isinstance(row, dict):
            out.append(f"{name} н/д")
            continue
        out.append(f"{name} {row.get('hits')}/{row.get('total')} "
                   f"{100 * float(row.get('rate', 0.0)):.1f}%")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("v5_run", type=Path)
    parser.add_argument("v4_run", type=Path)
    parser.add_argument("--public", action="store_true",
                        help="напечатать публичную подстроку (файл пишется всегда)")
    args = parser.parse_args()
    written = write(args.v5_run, args.v4_run, METRIC_FUNCTIONS)
    print(json.dumps(public(written.document) if args.public else written.document,
                     ensure_ascii=False, indent=2, sort_keys=True))
    print(f"\n{written.report}\n{written.public}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
