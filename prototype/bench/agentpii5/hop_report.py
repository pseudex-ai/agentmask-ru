"""Offline completed-cohort report: historical metrics beside actual OUT events
and actual CAUSAL hops.

No provider, engine, or judge is called. Output must be a new directory so
historical evidence cannot be overwritten by a new estimator.

THREE ESTIMATORS, THREE LABELS, NEVER MERGED. The historical lines are the
SCHEDULED-hop composition (`metrics.py`, `case.hops` as the clock); the actual
OUT lines are `actual_hops.py` (leaf identity and restoration); the causal lines
are `causal_hops.py` (which earlier artefact the agent was carrying, proved from
the recorded provider chronology). A rate from one may not be read as a rate of
another, and each section says which estimator printed it.
"""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from bench.agentpii5 import causal_hops, metrics
from bench.agentpii5.actual_hops import ActualAggregate, actual_events, aggregate
from bench.agentpii5.causal_hops import CausalAggregate, causal_events
from bench.agentpii5.cohort import Cohort, SourceSpec, cohort_to_json, compose_cohort


HISTORICAL_METRICS: tuple[str, ...] = (
    "leak", "coverage", "residual", "end_to_end", "form_hIN", "form_hOUT",
    "chain_value", "chain_form", "consistency", "memory_consistency",
    "multi_all_out", "overmask", "out_absent",
)
# `-2` adds the causal section. The number moves because the report's schema
# moved: a reader who pinned `-1` must not receive a file with a new block under
# the old name.
REPORT_VERSION: str = "hop-cohort-report-2"


def source_spec(value: str) -> SourceSpec:
    label: str
    directory: str
    label, separator, directory = value.partition("=")
    if not separator or not label.strip() or not directory:
        raise argparse.ArgumentTypeError("source must be LABEL=/absolute/run/directory")
    return SourceSpec(label=label, run_dir=Path(directory).resolve())


def historical_counts(cohort: Cohort) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for name in HISTORICAL_METRICS:
        line: metrics.Line = metrics.METRIC_FUNCTIONS[name](cohort.observations)
        counts[name] = {"hits": line.hits, "total": line.total}
    return counts


def ratio(hits: int, total: int) -> str:
    return f"{hits}/{total} ({100 * hits / total:.2f}%)" if total else "0/0 (not measured)"


def summary_text(cohort: Cohort, historical: dict[str, dict[str, int]],
                 actual: ActualAggregate, causal: CausalAggregate) -> str:
    rows: list[str] = [
        "# Completed cohort: historical, actual-hop and causal estimators",
        "",
        f"Report: `{REPORT_VERSION}`; actual OUT: `{actual.estimator}`; "
        f"causal: `{causal.estimator}`.",
        f"Complete triples: {len(cohort.observations)}; configuration groups: {len(cohort.config_groups)}.",
        "",
        "These are the SAME saved generations, NOT an engine improvement or a new live run.",
        "Actual OUT is a conservative diagnostic of tool leaves, not a replacement for behaviour, IN, answer or chain metrics.",
        "The causal section reads the recorded provider chronology only; a missing boundary is not_identifiable, never a pass.",
        "Unattributed/ambiguous/not_identifiable events are measurement uncertainty, not established gateway failures.",
        "Old traces have no model-response boundaries: an earlier executed tool in the SAME turn does not prove the agent saw its result.",
        "Full PHONE value is notation-independent. Other types retain legacy value predicates; whole/part aliasing can overcount ambiguity.",
        "",
        "## Historical estimator (SCHEDULED hops, completed-only composition)",
        "",
        "| Metric | Hits/total |",
        "|---|---:|",
    ]
    rows.extend(f"| {name} | {ratio(line['hits'], line['total'])} |"
                for name, line in historical.items())
    rows.extend([
        "", "The historical end_to_end/chain/multi lines still depend on scheduled hops.",
        "Do not interpret those rates as engine-only restoration quality, and do not",
        "read them beside the causal lines below as one table.",
        "", "## Actual OUT crossings (actual leaves, M0 estimator)", "",
        f"All leaf events: {actual.events_total}; not_applicable: {actual.not_applicable}.",
        "Each denominator below is the candidate leaf population, including uncertainty.",
        "Form is independent of identity; joint requires correct value, form and no residual.",
        "",
        "| Type | Candidates | Attributed | Value | Form | Form unmeasured | Residual present | Joint |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for item in (actual.overall,) + actual.by_type:
        count: int = item.candidates
        values: tuple[str, ...] = tuple(ratio(value, count) for value in (
            item.attributed, item.value_ok, item.form_ok, item.form_unmeasured,
            item.residual, item.joint_ok))
        rows.append(f"| {item.pii_type or 'untyped'} | {count} | " + " | ".join(values) + " |")
    rows.extend(["", "### Overall status counts", ""])
    rows.extend(f"- {status}: {count}" for status, count in actual.overall.statuses)
    rows.extend([
        "", "## Actual causal hops (recorded chronology, M03 estimator)", "",
        "General answer mentions, acting leaves and result-A->call-B edges have SEPARATE",
        "denominators. `attributed` means exactly ONE result is proved to have been in the",
        "model's hands, by the response boundary it was written in; several sufficient",
        "causes are `ambiguous`, an unprovable boundary is `not_identifiable`, and a datum",
        "the customer supplied is `user_provided` (excluded from the causal denominator).",
        "",
    ])
    rows.extend(causal_hops.render(causal))
    rows.extend([
        "", "## Provenance and spend", "",
        "`manifest.json` pins sources, recorded configurations, exclusions and ledger reconciliation.",
        "Recorded ledger cost is not a provider invoice; missing/unreconciled amounts remain visible.",
        "`events.jsonl` exposes each decision and its evidence for independent review.",
        "`report.json` pins scorer hashes. Retain all files together.", "",
    ])
    return "\n".join(rows)


def write_report(sources: tuple[SourceSpec, ...], output: Path) -> ActualAggregate:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite report directory: {output}")
    cohort: Cohort = compose_cohort(sources)
    observed = tuple(actual_events(one.case, one.run) for one in cohort.observations)
    actual: ActualAggregate = aggregate(observed)
    causal: CausalAggregate = causal_hops.aggregate(
        tuple(causal_events(one.case, one.run) for one in cohort.observations))
    historical: dict[str, dict[str, int]] = historical_counts(cohort)
    code_root: Path = Path(__file__).parent
    scorer_hashes: dict[str, str] = {
        name: hashlib.sha256((code_root / name).read_bytes()).hexdigest()
        for name in ("cohort.py", "actual_hops.py", "causal_hops.py", "hop_report.py",
                     "observe.py", "metrics.py", "form.py", "contracts.py", "tools.py")
    }
    payload: dict[str, object] = {
        "report_version": REPORT_VERSION,
        "cohort_fingerprint": cohort.fingerprint,
        "scorer_sha256": scorer_hashes,
        "historical": historical,
        "actual": asdict(actual),
        "causal": asdict(causal),
        "limitations": [
            "Actual tool leaves only; not full pipeline or behavioural equivalence",
            "Unknown/ambiguous attribution is measurement uncertainty",
            "Historical IN/answer/chain scores are not repaired by this report",
            "No LLM generation or engine replay; saved outcomes only",
            "Non-PHONE value predicates and free-text needles retain historical limitations",
            "Whole/part records of one entity may remain conservatively ambiguous",
            "Same-turn tool-result knowledge is not identifiable without recorded model-response boundaries",
            "Causal verdicts bind whole recorded substitute surfaces; partial-role leaves are the actual-OUT track's question",
            "A causal result-A->call-B edge proves the datum was available, never that the model reasoned from it",
        ],
    }
    # Compute first. A failed evaluation must not leave a seemingly complete report.
    manifest_text: str = json.dumps(cohort_to_json(cohort), ensure_ascii=False, indent=2) + "\n"
    report_text: str = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    event_text: str = "".join(json.dumps(asdict(event), ensure_ascii=False) + "\n"
                              for one in observed for event in one.events)
    markdown: str = summary_text(cohort, historical, actual, causal)
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_text(manifest_text, encoding="utf-8")
    (output / "report.json").write_text(report_text, encoding="utf-8")
    (output / "events.jsonl").write_text(event_text, encoding="utf-8")
    (output / "summary.md").write_text(markdown, encoding="utf-8")
    return actual


def main() -> int:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", type=source_spec, required=True,
                        help="LABEL=/absolute/run/directory; repeat for each source")
    parser.add_argument("--out", type=Path, required=True, help="A new output directory")
    args: argparse.Namespace = parser.parse_args()
    result: ActualAggregate = write_report(tuple(args.source), args.out)
    print(f"{result.runs} complete triples; {result.events_total} actual leaves; "
          f"estimator={result.estimator}; report={args.out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
