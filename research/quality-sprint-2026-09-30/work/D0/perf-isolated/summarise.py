#!/usr/bin/env python3
"""Aggregate the O-DETECT isolated perf raw rows into `summary.json`.

Recomputes every percentile FROM THE RAW TSV rather than trusting the numbers a
run wrote into its own `.meta.json`, then cross-checks the two and records any
disagreement instead of silently preferring one. The raw TSV is the source of
truth; the meta file is a convenience.

Reporting rules this file is built around (RUNBOOK-PERF §3):
  * spread is never averaged away — every run is printed, and each metric carries
    min / max / range / stdev across runs next to its p50-of-runs;
  * the headline for a metric is the MEDIAN ACROSS RUNS ("p50 of the p50s"),
    because a single run's p50 is not a p50;
  * a pooled percentile over all runs' samples is computed too, but is marked
    `headline: false`: it is the exact quantity that hides between-run spread;
  * a run whose frozen-input hashes disagree with its siblings marks the whole
    experiment VOID (RUNBOOK-PERF §0.2) rather than being dropped quietly.

Usage:
    PYTHONDONTWRITEBYTECODE=1 python3 summarise.py --raw-dir <run>/raw \
        --out <run>/summary.json [--env <run>/env.json]
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import perf_common as pc  # noqa: E402

ARMS = ("FULL", "NER_ONLY")
# The head of the per-run report row, exactly as RUNBOOK-PERF §2 writes it.
REPORT_COLUMNS = ("arm", "repeat", "cold_start_ms", "p50", "p95", "p99", "mean",
                  "stdev", "rss_after_import_mb", "rss_after_load_mb",
                  "rss_after_warmup_mb", "rss_after_n_mb", "throughput_msg_s",
                  "model_bytes", "corpus_sha256", "module_manifest_sha256")
SPREAD_METRICS = ("cold_start_ms", "p50", "p95", "p99", "mean", "stdev", "max",
                  "throughput_msg_s", "rss_after_import_mb", "rss_after_load_mb",
                  "rss_after_warmup_mb", "rss_after_n_mb",
                  "cur_rss_after_n_mb", "time_to_warm_ms", "warmup_max_ms")
POOLED_METRICS = ("p50", "p95", "p99", "mean", "max")


def read_tsv(path: Path) -> tuple[dict, list[dict]]:
    header: list[str] = []
    rows: list[dict] = []
    notes: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            if line.startswith("#"):
                body = line.lstrip("# ").strip()
                if "=" in body:
                    key, _, value = body.partition("=")
                    notes[key.strip()] = value.strip()
                continue
            parts = line.split("\t")
            if not header:
                header = parts
                continue
            rows.append(dict(zip(header, parts)))
    return notes, rows


def read_time_l(log_path: Path) -> dict:
    """`/usr/bin/time -l` process-level numbers from the runner's log.

    An INDEPENDENT check on the in-process `ru_maxrss`: it is the kernel's own
    accounting for the whole child process, so a disagreement between the two is
    evidence of a measurement problem rather than a rounding difference.
    macOS prints the VALUE FIRST and the label after it, with no colon
    (`           466878464  maximum resident set size`), while GNU `time -v`
    prints `Maximum resident set size (kbytes): 456`. Both forms are parsed and
    the unit is recorded, because the first version of this parser only knew the
    colon form and silently produced an empty cross-check column.
    """
    if not log_path.exists():
        return {}
    text = log_path.read_text(encoding="utf-8", errors="replace")
    out: dict = {"log": log_path.name}
    match = re.search(r"(\d+)\s+maximum resident set size", text)
    if match:
        out["peak_rss_units"] = "bytes"
        out["peak_rss_bytes"] = int(match.group(1))
        out["peak_rss_mb"] = round(int(match.group(1)) / (1024 * 1024), 1)
    else:
        match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", text)
        if match:
            out["peak_rss_units"] = "KiB"
            out["peak_rss_bytes"] = int(match.group(1)) * 1024
            out["peak_rss_mb"] = round(int(match.group(1)) / 1024, 1)
    match = re.search(r"([\d.]+)\s+real\b", text)
    if match:
        out["real_s"] = float(match.group(1))
    match = re.search(r"([\d.]+)\s+user\b", text)
    if match:
        out["user_s"] = float(match.group(1))
    match = re.search(r"([\d.]+)\s+sys\b", text)
    if match:
        out["sys_s"] = float(match.group(1))
    return out


def spread(values: list[float]) -> dict:
    clean = [v for v in values if v is not None]
    if not clean:
        return {}
    out = {"n": len(clean), "min": round(min(clean), 4),
           "max": round(max(clean), 4),
           "range": round(max(clean) - min(clean), 4),
           "median": round(statistics.median(clean), 4)}
    if len(clean) > 1:
        out["stdev"] = round(statistics.stdev(clean), 4)
        out["spread_ratio_max_over_min"] = (
            round(max(clean) / min(clean), 3) if min(clean) > 0 else None)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--env", default=None)
    ap.add_argument("--logs-dir", default=None,
                    help="runner logs; enables the /usr/bin/time -l cross-check")
    ap.add_argument("--expected-repeats", type=int, default=5,
                    help="RUNBOOK-PERF wants 5; the executed count is recorded "
                         "and any shortfall is reported, not hidden")
    args = ap.parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    out_path = Path(args.out).resolve()
    logs_dir = Path(args.logs_dir).resolve() if args.logs_dir else None

    metas = []
    for meta_file in sorted(raw_dir.glob("*-run*.meta.json")):
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        tsv = meta_file.with_suffix("").with_suffix(".tsv")
        if not tsv.exists():
            raise SystemExit(f"meta without raw rows: {meta_file} -> {tsv}")
        notes, rows = read_tsv(tsv)
        timed = [float(r["detect_ms"]) for r in rows if r["phase"] == "timed"]
        phases = collections.Counter(r["phase"] for r in rows)
        recomputed = {
            "p50": round(pc.pct(timed, 0.50), 4),
            "p95": round(pc.pct(timed, 0.95), 4),
            "p99": round(pc.pct(timed, 0.99), 4),
            "mean": round(statistics.mean(timed), 4),
            "stdev": round(statistics.stdev(timed), 4) if len(timed) > 1 else None,
            "max": round(max(timed), 4),
            "n": len(timed),
        }
        drift = {k: {"meta": meta.get(k), "recomputed": recomputed[k]}
                 for k in ("p50", "p95", "p99", "mean", "stdev", "max")
                 if meta.get(k) is not None
                 and abs(float(meta[k]) - float(recomputed[k])) > 1e-6}
        metas.append({
            "meta_file": str(meta_file.relative_to(raw_dir.parent)),
            "tsv_file": str(tsv.relative_to(raw_dir.parent)),
            "arm": meta["arm"], "repeat": meta["repeat"],
            "rows": dict(phases),
            "timed_rows": len(timed),
            "recomputed_from_raw": recomputed,
            "meta_vs_raw_disagreements": drift,
            "meta": meta,
            "samples_ms": timed,
            "time_l": (read_time_l(logs_dir / f"run-{meta['arm']}-run{meta['repeat']}.log")
                       if logs_dir else {}),
        })

    if not metas:
        raise SystemExit(f"no *-run*.meta.json under {raw_dir}")

    # Frozen-input consistency: one experiment, one input set.
    corpus_hashes = sorted({m["meta"]["corpus_sha256"] for m in metas})
    manifest_hashes = sorted({m["meta"]["module_manifest_sha256"] for m in metas})
    bundle_versions = sorted({str(m["meta"].get("bundle_version")) for m in metas})
    model_bytes = sorted({m["meta"]["model_bytes"] for m in metas})
    drift_free = (len(corpus_hashes) == 1 and len(manifest_hashes) == 1
                  and len(bundle_versions) == 1 and len(model_bytes) == 1)
    any_meta_drift = any(m["meta_vs_raw_disagreements"] for m in metas)

    summary: dict = {
        "title": "O-DETECT isolated detector resource experiment — summary",
        "status": "EXPLORATORY_PRELIMINARY",
        "status_reasons": [
            "3 repeats per arm executed; RUNBOOK-PERF §1 wants k=5",
            "host was NOT isolated: another repo benchmark job "
            "(`python -m bench.agentpii5.live`) held ~1 core for the whole run",
        ],
        "scope": ("cost measurement only; no quality number, no production "
                  "equivalence, no architecture recommendation"),
        "headline_metric_definition": (
            "MEDIAN ACROSS RUNS of the per-run percentile (p50 of the p50s). "
            "Pooled percentiles are provided but flagged headline=false because "
            "they hide between-run spread."),
        "percentile_definition": pc.PCT_DEFINITION,
        "read_from": "raw TSVs recomputed here; each run's .meta.json cross-checked",
        "raw_files": [m["tsv_file"] for m in metas],
        "frozen_inputs": {
            "corpus_sha256": corpus_hashes, "corpus_unique": len(corpus_hashes) == 1,
            "module_manifest_sha256": manifest_hashes,
            "module_manifest_unique": len(manifest_hashes) == 1,
            "bundle_version": bundle_versions,
            "model_bytes": model_bytes,
            "consistent": drift_free,
            "void_if_inconsistent": not drift_free,
            "meta_vs_raw_disagreement_any": any_meta_drift,
        },
        "repeats": {
            "required_by_runbook": args.expected_repeats,
            "per_arm": {arm: sorted(m["repeat"] for m in metas if m["arm"] == arm)
                        for arm in ARMS},
        },
        "arms": {},
        "executed_utc_wall_span": None,
    }

    for arm in ARMS:
        runs = [m for m in metas if m["arm"] == arm]
        if not runs:
            summary["arms"][arm] = {"measured": False,
                                    "note": "NOT_MEASURED — no raw run found"}
            continue
        runs.sort(key=lambda m: m["repeat"])
        entry: dict = {
            "measured": True,
            "arm_kind": runs[0]["meta"]["arm_kind"],
            "n_per_run": sorted({m["meta"]["n"] for m in runs}),
            "warmup_per_run": sorted({m["meta"]["warmup"] for m in runs}),
            "warmup_selection": runs[0]["meta"].get("warmup_selection"),
            "corpus_messages": runs[0]["meta"]["corpus_messages"],
            "unique_timed_texts_per_run": sorted(
                {m["meta"]["unique_timed_texts"] for m in runs}),
            "runs": [{
                "repeat": m["repeat"],
                "raw": m["tsv_file"],
                "timed_rows": m["timed_rows"],
                "row_phases": m["rows"],
                **{k: m["meta"].get(k) for k in REPORT_COLUMNS
                   if k not in ("arm", "repeat")},
                "max": m["meta"].get("max"),
                "min": m["meta"].get("min"),
                "cur_rss_after_n_mb": m["meta"].get("cur_rss_after_n_mb"),
                "time_to_warm_ms": m["meta"].get("time_to_warm_ms"),
                "warmup_max_ms": m["meta"].get("warmup_max_ms"),
                "import_ms": m["meta"].get("import_ms"),
                "bundle_load_ms": m["meta"].get("bundle_load_ms"),
                "model_load_ms": m["meta"].get("model_load_ms"),
                "controls": m["meta"].get("controls"),
                "meta_vs_raw_disagreements": m["meta_vs_raw_disagreements"],
                "time_l_process_peak": m["time_l"],
            } for m in runs],
            "spread_across_runs": {
                key: spread([m["meta"].get(key) for m in runs])
                for key in SPREAD_METRICS},
        }
        # p50 of the p50s, and the same median-across-runs shape for the rest.
        entry["median_across_runs"] = {
            key: (spread([m["meta"].get(key) for m in runs]).get("median"))
            for key in SPREAD_METRICS}
        summary["arms"][arm] = entry

    # Pooled percentiles — provably hide between-run spread. Kept, flagged.
    summary["pooled_all_samples"] = {
        "headline": False,
        "why_not_headline": "pooling k runs of N samples into one distribution "
                            "removes the between-run spread RUNBOOK-PERF §1 asks "
                            "to be shown",
        "per_arm": {arm: ({key: round(pc.pct(
            [v for m in metas if m["arm"] == arm for v in m["samples_ms"]],
            p), 4) for key, p in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99))}
            | {"mean": round(statistics.mean(
                [v for m in metas if m["arm"] == arm for v in m["samples_ms"]]), 4),
               "samples": sum(m["timed_rows"] for m in metas if m["arm"] == arm)}
            if any(m["arm"] == arm for m in metas) else None)
            for arm in ARMS},
    }

    if args.env and Path(args.env).exists():
        summary["environment"] = json.loads(Path(args.env).read_text(encoding="utf-8"))

    # The runbook's own one-row-per-run report shape, so a later reader can diff
    # it against another runbook run without re-deriving anything.
    report_tsv = raw_dir / "report-lines.tsv"
    with report_tsv.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(REPORT_COLUMNS) + "\n")
        for m in sorted(metas, key=lambda x: (x["arm"], x["repeat"])):
            meta = m["meta"]
            handle.write("\t".join(str(meta.get(col, ""))
                                   for col in REPORT_COLUMNS) + "\n")
    summary["report_lines_tsv"] = str(report_tsv.relative_to(out_path.parent))
    peaks_in_process = [m["meta"].get("rss_after_n_mb") for m in metas
                        if m["meta"].get("rss_after_n_mb") is not None]
    peaks_time_l = [round(m["time_l"]["peak_rss_bytes"] / (1024 * 1024), 1)
                    for m in metas if m["time_l"].get("peak_rss_bytes")]
    peak_agreement = (None if len(peaks_in_process) != len(peaks_time_l)
                      else max(abs(a - b) for a, b in
                               zip(peaks_in_process, peaks_time_l)))
    summary["instrument_integrity"] = {
        "peak_rss_in_process_mb": peaks_in_process,
        "peak_rss_time_l_mb": peaks_time_l,
        "max_abs_peak_rss_disagreement_mb": peak_agreement,
        "peak_rss_crosscheck": ("AGREE_WITHIN_1MB" if peak_agreement is not None
                                and peak_agreement <= 1.0 else
                                "DISAGREE_OR_MISSING — investigate"),
        "meta_vs_raw_recompute_disagreements": any_meta_drift,
        "all_runs_share_frozen_inputs": drift_free,
        "verdict": ("OK" if drift_free and not any_meta_drift
                    else "VOID_OR_DRIFT — do not use these numbers"),
    }

    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")

    print(f"summary written: {out_path}")
    print(f"  frozen inputs consistent: {drift_free}   "
          f"meta/raw recompute clean: {not any_meta_drift}")
    for arm in ARMS:
        entry = summary["arms"][arm]
        if not entry.get("measured"):
            print(f"  {arm}: NOT_MEASURED")
            continue
        med = entry["median_across_runs"]
        pc50 = entry["spread_across_runs"].get("p50", {})
        pc95 = entry["spread_across_runs"].get("p95", {})
        print(f"  {arm}: median-across-runs p50={med.get('p50')} "
              f"p95={med.get('p95')} p99={med.get('p99')} "
              f"ms | p50 spread {pc50.get('min')}..{pc50.get('max')} "
              f"| p95 spread {pc95.get('min')}..{pc95.get('max')} "
              f"| runs={len(entry['runs'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
