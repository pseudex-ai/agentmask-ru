#!/usr/bin/env python3
"""Freeze the inputs and record the isolation state for the O-DETECT perf run.

Writes, all inside this run's own scope:
  * `env.json`               — RUNBOOK-PERF §0.2 frozen identity: git HEAD, every
                               `prototype/pseudex/*.py` + `prototype/licensing/*.py`
                               hash, the in-memory bundle identity from
                               `build_plaintext()`, model-weight hashes, the corpus
                               sha256, python/libraries, and the isolation snapshot
                               taken BEFORE the first measurement.
  * `isolation-start.json` / `isolation-end.json` — the two host snapshots
                               (`--isolation-out`), so a reader can see whether the
                               contended state held for the whole window.
  * `INPUTS.json`            — authorization, write scope, the forbidden list and
                               what was actually read (`--write-inputs`).

Nothing here writes outside this folder, and nothing here loads a model.
"""

from __future__ import annotations

import argparse
import json
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
PROTO = REPO / "prototype"
for entry in (str(HERE), str(PROTO)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import perf_common as pc  # noqa: E402

REPO_ROOT = REPO
SCOPE = "research/quality-sprint-2026-09-30/work/D0/perf-isolated/"

# Heuristics for "another heavy job", deliberately crude and PRINTED so a reader
# can disagree with the verdict: >40% CPU is the threshold, and the job's own
# command line is kept in the output.
HEAVY_CPU_PCT = 40.0
HEAVY_HINTS = ("bench", "agentpii", "eval", "ner", "pytest", "uvicorn", "docker",
               "nuitka", "gates.py")


def sh(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=False,
                              cwd=str(REPO_ROOT)).stdout.strip()
    except Exception as exc:                      # pragma: no cover
        return f"<failed: {exc}>"


def isolation_snapshot(label: str) -> dict:
    """uptime, load average and the top CPU processes, as RUNBOOK-PERF §2 step 0."""
    uptime = sh(["uptime"])
    loadavg = None
    if platform.system() == "Darwin":
        raw = sh(["sysctl", "-n", "vm.loadavg"])
        loadavg = raw.strip("{} ").split() if raw else None
    else:
        try:
            loadavg = list(__import__("os").getloadavg())
        except Exception:
            loadavg = None

    snapshot: dict = {
        "label": label,
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "captured_epoch": round(time.time(), 3),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "uptime": uptime,
        "loadavg": loadavg,
        "cpu_count": __import__("os").cpu_count(),
        "top_cpu": [],
        "heavy_jobs": [],
    }
    ps_out = sh(["ps", "-Ao", "%cpu=,pid=,rss=,etime=,command=", "-r"])
    own = {"PID": None}
    for line in ps_out.splitlines()[:15]:
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        cpu, pid, rss, etime, command = parts
        row = {"cpu_pct": float(cpu), "pid": int(pid), "rss_kb": int(rss),
               "etime": etime, "command": command}
        snapshot["top_cpu"].append(row)
        low = command.lower()
        if (row["cpu_pct"] >= HEAVY_CPU_PCT
                and any(hint in low for hint in HEAVY_HINTS)
                and "make_env.py" not in low):
            snapshot["heavy_jobs"].append(row)
    snapshot["verdict"] = ("NOT_ISOLATED" if snapshot["heavy_jobs"] else "ISOLATED")
    snapshot["threshold_cpu_pct"] = HEAVY_CPU_PCT
    snapshot["hints"] = list(HEAVY_HINTS)
    snapshot["note"] = (
        "RUNBOOK-PERF §0.1 requires no other NER/container/benchmark job. A "
        "NOT_ISOLATED verdict makes every number EXPLORATORY: it may not enter an "
        "admission budget (RUNBOOK-PERF §3)."
    )
    return snapshot


def git_info() -> dict:
    return {
        "head": sh(["git", "rev-parse", "HEAD"]),
        "branch": sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "head_subject": sh(["git", "log", "-1", "--format=%s"]),
        "head_committed_at": sh(["git", "log", "-1", "--format=%cI"]),
        "status_porcelain_prototype": [
            line for line in sh(["git", "status", "--porcelain", "--",
                                 "prototype"]).splitlines() if line.strip()],
        "status_porcelain_scope": [
            line for line in sh(["git", "status", "--porcelain", "--",
                                 SCOPE]).splitlines() if line.strip()],
        "status_porcelain_repo_count": len(
            [line for line in sh(["git", "status", "--porcelain"]).splitlines()
             if line.strip()]),
        "note": ("read-only `git rev-parse` / `git status`; no stash, reset, "
                 "checkout or revert was issued at any point in this run"),
    }


def build_env(args) -> dict:
    corpus = Path(args.corpus).resolve()
    manifest = pc.module_manifest()
    return {
        "task": "O-DETECT isolated detector resource experiment (preliminary pass)",
        "runbook": "work/D0/RUNBOOK-PERF.md",
        "scope_write_only": SCOPE,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git": git_info(),
        "product_source_pin_reference": (
            "B0/SPEC record product source pinned at "
            "0bfda2363ef1a1d552e2ac093129b1026a86ad68; this run measured the "
            "working tree at the HEAD above and did not change it"),
        "module_manifest_sha256": pc.manifest_sha256(manifest),
        "module_count": len(manifest),
        "module_hashes": dict(sorted(manifest.items())),
        "bundle_identity": pc.bundle_identity(),
        "model_weights": pc.model_files(),
        "model_bytes_total": pc.model_bytes_total(),
        "corpus": {
            "path": str(corpus),
            "sha256": pc.corpus_sha256(corpus),
            "messages": len(pc.load_corpus(corpus)),
            "seed": 20260930,
            "generator": "perf-isolated/gen_corpus.py",
            "provenance": ("fully synthetic from the templates in gen_corpus.py; "
                           "no real-speech utterance, no transcript, no "
                           "prototype/*.json dataset, no holdout and no paid-run "
                           "file was read"),
        },
        "runtime": {
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "PYTHONDONTWRITEBYTECODE": __import__("os").environ.get(
                "PYTHONDONTWRITEBYTECODE"),
            "cpu_count": __import__("os").cpu_count(),
            "total_memory_bytes": _total_memory(),
            "libraries": pc.libraries(),
        },
        "isolation": isolation_snapshot("start"),
        "preconditions": {
            "0.1_isolation": "FAIL — see isolation.heavy_jobs; numbers are EXPLORATORY",
            "0.2_frozen_inputs": "PASS — hashes recorded here before measurement",
            "0.3_fixed_corpus_not_holdout": "PASS — own synthetic corpus, sha256 above",
            "0.4_no_new_software": "PASS — nothing installed or downloaded",
            "0.5_one_process_per_arm_sequential": "PASS — separate `python` process "
                                                  "per arm per repeat",
            "repeats_k5": "NOT_MET — 3 repeats executed; this is a preliminary pass",
        },
        "reporting_rules_applied": [
            "never average away spread: per-run values + min/max/range/stdev",
            "headline is median-across-runs, not a pooled percentile",
            "no quality claim, no production equivalence, no adoption advice",
            "contended host => EXPLORATORY, not budget-grade",
        ],
    }


def _total_memory() -> int | None:
    try:
        if platform.system() == "Darwin":
            return int(sh(["sysctl", "-n", "hw.memsize"]) or 0) or None
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        return None
    return None


def write_inputs(args, env: dict) -> None:
    inputs = {
        "task": "O-DETECT — isolated detector resource experiment (preliminary pass)",
        "folder": SCOPE,
        "created_utc": env["created_utc"],
        "root": str(REPO_ROOT),
        "authorization": {
            "runbook": "work/D0/RUNBOOK-PERF.md",
            "spec": "work/D0/SPEC.md",
            "metrics_correction": "work/contracts-revision-2/D0-METRICS-CORRECTED.md",
            "requirement": ("REMAINING-DECISIONS block 4 / SPRINT-PLAN §7 — the "
                            "measured CPU/RAM/latency numbers O-DETECT needs "
                            "before any mechanism is adopted"),
            "write_scope": SCOPE,
        },
        "model_routing": {
            "requested_provider": "deepseek-official",
            "requested_model": "deepseek-flash",
            "effective_model": "NOT_AVAILABLE_FROM_RUNTIME",
            "note": ("routing metadata was not exposed to this agent; no "
                     "self-identity attestation is made and no other model name "
                     "is claimed — self-identity is not proof of routing"),
        },
        "revision": env["git"],
        "read": [
            "work/D0/RUNBOOK-PERF.md",
            "work/D0/SPEC.md",
            "work/contracts-revision-2/D0-METRICS-CORRECTED.md",
            "work/D0/INPUTS.json (format reference)",
            "prototype/pseudex/detect_all.py, assets.py, ru_pii.py, address.py (read-only)",
            "prototype/licensing/pack.py, prototype/testkit.py (read-only)",
        ],
        "not_read": [
            "the 359-ID holdout (no holdout file exists in prototype/ and none was opened)",
            "the paid-run directory",
            "any corpus of real speech copied into artifacts",
        ],
        "forbidden_and_honoured": [
            "no engine/licensing/scorer/corpus/wiki/git modification",
            "no install, download or model download",
            "no provider/production/paid call",
            "no holdout (359-ID) read; no paid-run directory read",
            "no stash/reset/revert/checkout",
            "no writes outside the scope folder",
        ],
        "inputs_frozen": {
            "corpus_sha256": env["corpus"]["sha256"],
            "module_manifest_sha256": env["module_manifest_sha256"],
            "module_count": env["module_count"],
            "bundle_identity": env["bundle_identity"],
            "model_weights": env["model_weights"],
        },
        "outputs": [
            "INPUTS.json", "env.json", "isolation-start.json", "isolation-end.json",
            "corpus.jsonl", "corpus.sha256", "corpus.meta.json",
            "perf_common.py", "gen_corpus.py", "make_env.py",
            "perf_one_arm.py", "summarise.py",
            "raw/<arm>-run<k>.tsv", "raw/<arm>-run<k>.meta.json",
            "raw/report-lines.tsv", "summary.json", "GATE.json", "REPORT.md",
            "logs/*.log",
        ],
        "arms": {
            "FULL": "current Detector.detect (detect_all) — product path in-process",
            "NER_ONLY": ("diagnostic ablation: Natasha PER/LOC only, rules layer "
                         "disabled; NOT a production candidate"),
        },
        "status": "EXPLORATORY_PRELIMINARY — contended host, 3 repeats not 5",
    }
    (Path(args.out).resolve() / "INPUTS.json").write_text(
        json.dumps(inputs, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="this run's folder")
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--isolation-out", default=None)
    ap.add_argument("--env-isolation", default=None,
                    help="embed THIS snapshot in env.json instead of taking a "
                         "fresh one; env.json must carry the PRE-measurement "
                         "snapshot even when it is re-emitted afterwards")
    ap.add_argument("--env-isolation-ref", default=None)
    ap.add_argument("--write-inputs", action="store_true")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = build_env(args)
    # The isolation block in env.json must be the snapshot taken BEFORE the first
    # measurement. Re-emitting env.json after the run (which this script does, to
    # capture the end state) must not silently replace that block with a later
    # one — the first version of this script did exactly that.
    env["env_emitted_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if args.env_isolation:
        embedded = json.loads(Path(args.env_isolation).read_text(encoding="utf-8"))
        env["isolation"] = embedded
        env["created_utc"] = embedded.get("captured_utc", env["created_utc"])
        env["isolation_source"] = str(Path(args.env_isolation).name)
    if args.env_isolation_ref:
        env["isolation_end_ref"] = args.env_isolation_ref
    (out / "env.json").write_text(json.dumps(env, ensure_ascii=False, indent=1) + "\n",
                                  encoding="utf-8")
    if args.isolation_out:
        snap = isolation_snapshot(Path(args.isolation_out).stem)
        Path(args.isolation_out).write_text(
            json.dumps(snap, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"isolation [{snap['label']}]: {snap['verdict']} "
              f"loadavg={snap['loadavg']}")
        for job in snap["heavy_jobs"]:
            print(f"  heavy: pid={job['pid']} cpu={job['cpu_pct']}% "
                  f"etime={job['etime']} {job['command'][:120]}")
    if args.write_inputs:
        write_inputs(args, env)
    print(f"env.json: HEAD={env['git']['head'][:12]} "
          f"modules={env['module_count']} "
          f"manifest={env['module_manifest_sha256'][:16]} "
          f"bundle={env['bundle_identity']['version']} "
          f"({env['bundle_identity']['bytes']} B, "
          f"{env['bundle_identity']['sha256'][:16]})")
    print(f"corpus: {env['corpus']['messages']} msgs sha256={env['corpus']['sha256']}")
    print(f"model bytes: {env['model_bytes_total']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
