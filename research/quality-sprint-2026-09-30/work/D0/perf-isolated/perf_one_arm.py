#!/usr/bin/env python3
"""One arm, one process: the O-DETECT isolated per-message latency/RSS pass.

Pattern copied from `prototype/profile_latency.py` (warm-up, p50/p95, in-process
RSS) into THIS scope, as RUNBOOK-PERF §2 requires — `profile_latency.py` itself
reads `holdout.json`, which must not be manufactured here, and editing a shared
benchmark file would collide with the single-benchmark-writer rule.

WHAT ONE RUN DOES (RUNBOOK-PERF §1), in this order:
  1. import the engine modules                          -> rss_after_modules_mb
  2. `testkit.load_dev_bundle()` (the dev lease path)   -> rss_after_import_mb
  3. construct the arm (loads natasha weights)          -> rss_after_load_mb
  4. one COLD call (timed; this is the cold-start number)
  5. N_WARMUP further calls, discarded                   -> rss_after_warmup_mb
  6. N >= 1000 timed calls, one corpus message per call  -> rss_after_n_mb
  7. percentiles over exactly those N samples

ARMS — exactly two, and NEITHER is a product recommendation:

  `FULL`      current `Detector.detect` — the whole pipeline as shipped in-process.
              Not the container image (no HTTP, no uvicorn, no worker fan-out).

  `NER_ONLY`  DIAGNOSTIC ABLATION, not a production candidate. It keeps ONLY the
              Natasha PER/LOC layer: `Detector._ner_spans(normalize(text))`.
              KEPT:       Layer 0 `normalize()`; natasha Segmenter + NewsNERTagger;
                          the in-layer gates `names.keep_person`, `names.keep_location`,
                          `context.location_is_pii`, `names.trim_person_span`.
              DISABLED:   detect_address, detect_pii (phone/email), detect_structured,
                          detect_structured_kv, detect_spoken_ids/_email/_plate,
                          detect_credentials, detect_vehicle_ids, detect_plates,
                          gazetteer_names, detect_quasi, context.suppress,
                          _resolve/_PRIORITY arbitration, and the ADDR-vs-NAME
                          `_guess_inside_person` cross-check.
              Consequence of disabling `_resolve`: spans may overlap and no
              priority winner is chosen. That does not affect cost, and no
              quality claim is made from either arm anywhere in this run.

Cold start needs a process-start reference, and a script cannot see its own
`exec`. So unless `--no-prespawn` is given, the script re-executes itself once
with `PERF_SPAWN_WALL` in the environment; the parent records `time.time()` right
before `subprocess.run`, and the child reports `first_detect_wall - spawn_wall`.
That number therefore includes fork/exec/dyld, which an in-process timer cannot.
`--no-prespawn` (or `PERF_CHILD=1`) measures from the script's first statement
instead and says so in `cold_start_origin`.

Outputs: `--out` (per-message TSV, one row per call, `phase` column) and, beside
it, the same stem with `.meta.json` (the RUNBOOK-PERF §2 report row plus
extras). Exit 3 if the FULL positive control sees no spans.
"""

import time as _time
_T0_PERF = _time.perf_counter()          # first statement in this file
_T0_WALL = _time.time()

import argparse                          # noqa: E402
import json                              # noqa: E402
import os                                # noqa: E402
import platform                          # noqa: E402
import statistics                        # noqa: E402
import subprocess                        # noqa: E402
import sys                               # noqa: E402
from pathlib import Path                 # noqa: E402

HERE = Path(__file__).resolve().parent
PROTO = HERE.parents[4] / "prototype"
for entry in (str(HERE), str(PROTO)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import perf_common as pc                 # noqa: E402

ARMS = ("FULL", "NER_ONLY")
POSITIVE_CONTROL = "Позвоните Иванову Ивану по телефону +79261234567"
NEGATIVE_CONTROL = ""


def _reexec(argv: list[str]) -> int:
    """Parent half of the cold-start measurement; see the module docstring."""
    spawn_wall = _time.time()
    env = dict(os.environ)
    env["PERF_CHILD"] = "1"
    env["PERF_SPAWN_WALL"] = repr(spawn_wall)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), *argv],
                          env=env)
    return proc.returncode


def _build_arm(name: str):
    """Import the engine, lease the dev bundle, and return (detector, callable)."""
    t_import = _time.perf_counter()
    from pseudex.detect_all import Detector            # noqa: PLC0415
    from pseudex.normalize import normalize            # noqa: PLC0415
    import testkit                                     # noqa: PLC0415
    import_ms = (_time.perf_counter() - t_import) * 1000
    rss_modules = pc.rss_mb()
    cur_modules = pc.current_rss_mb()

    t_bundle = _time.perf_counter()
    testkit.load_dev_bundle()
    bundle_ms = (_time.perf_counter() - t_bundle) * 1000
    rss_import = pc.rss_mb()
    cur_import = pc.current_rss_mb()

    from pseudex.assets import ASSETS                  # noqa: PLC0415
    bundle_version = ASSETS.version

    if name == "FULL":
        cls = Detector
    else:
        class _NerOnly(Detector):                      # documented ablation
            def detect(self, text):
                return self._ner_spans(normalize(text))

        cls = _NerOnly

    t_load = _time.perf_counter()
    detector = cls()
    load_ms = (_time.perf_counter() - t_load) * 1000
    rss_load = pc.rss_mb()
    cur_load = pc.current_rss_mb()

    return detector, detector.detect, {
        "import_ms": import_ms, "bundle_load_ms": bundle_ms,
        "model_load_ms": load_ms, "bundle_version": bundle_version,
        "rss_after_modules": rss_modules, "rss_after_import": rss_import,
        "rss_after_load": rss_load,
        "cur_after_modules": cur_modules, "cur_after_import": cur_import,
        "cur_after_load": cur_load,
    }


def _controls(call) -> dict:
    positive = call(POSITIVE_CONTROL)
    negative = call(NEGATIVE_CONTROL)
    return {
        "positive_spans": len(positive),
        "positive_types": sorted({getattr(s, "entity_type", "?") for s in positive}),
        "negative_spans": len(negative),
        "positive_text": POSITIVE_CONTROL,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=ARMS)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--warmup", type=int, default=50)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-prespawn", action="store_true",
                    help="measure cold start from script entry, not process spawn")
    args = ap.parse_args()

    if os.environ.get("PERF_CHILD") != "1" and not args.no_prespawn:
        return _reexec(sys.argv[1:])

    spawn_wall = os.environ.get("PERF_SPAWN_WALL")
    if spawn_wall is not None:
        spawn_wall = float(spawn_wall)
        cold_origin = "parent_recorded_before_subprocess_run"
    else:
        spawn_wall = _T0_WALL
        cold_origin = "script_entry_first_statement"

    corpus_path = Path(args.corpus).resolve()
    messages = pc.load_corpus(corpus_path)
    if not messages:
        raise SystemExit(f"empty corpus: {corpus_path}")
    texts = [m["text"] for m in messages]
    corpus_sha = pc.corpus_sha256(corpus_path)

    detector, call, phases = _build_arm(args.arm)

    # ---- 4) ONE cold call: the FIRST detect() this process ever makes -------
    # No calibration call is made before this one on purpose — RUNBOOK-PERF §1
    # defines cold start as process start to the first successful detect()
    # return, and a "warm the tagger first" call would silently move the lazy
    # model work out of the number it is supposed to contain.
    cold_text = texts[0]
    t_cold = _time.perf_counter()
    t_cold_wall = _time.time()          # same clock as the parent's spawn marker
    first = call(cold_text)
    cold_in_process_ms = (_time.perf_counter() - t_cold) * 1000
    cold_call = {"call_index": 0, "msg_index": 0, "chars": len(cold_text),
                 "spans": len(first), "detect_ms": cold_in_process_ms,
                 "phase": "cold"}
    # spawn_wall is epoch seconds (time.time) — the cold number MUST be computed
    # on the wall clock, not against perf_counter: the first version subtracted
    # an epoch value from a monotonic one and printed -1.79e12 ms.
    cold_start_ms = (t_cold_wall - spawn_wall) * 1000
    interpreter_startup_ms = (_T0_WALL - spawn_wall) * 1000

    # Instrument controls run AFTER the cold call so they cannot warm the path
    # the cold number is measuring.
    controls = _controls(call)
    if args.arm == "FULL" and controls["positive_spans"] < 2:
        print(f"INSTRUMENT FAILURE: FULL positive control saw "
              f"{controls['positive_spans']} spans, expected >= 2", file=sys.stderr)
        return 3
    if controls["negative_spans"] != 0:
        print(f"INSTRUMENT FAILURE: empty input produced "
              f"{controls['negative_spans']} spans", file=sys.stderr)
        return 3

    # ---- 5) warm-up, discarded -------------------------------------------
    # SPREAD, not the first N rows. Reason, measured in this run's own smoke
    # pass: `address.py::_street_index` builds a deletion index over the whole
    # leased ГАР street vocabulary (~165k names) on FIRST use — ~500 ms once per
    # process — and `Detector()` does NOT pay it. A warm-up over the first 50
    # contiguous corpus rows left that build inside the timed window and turned
    # p99 into a one-time setup cost. The spread touches every register before
    # timing starts, and the discarded cost is still PRINTED (warmup_max_ms) so
    # nothing is hidden by the choice.
    step = max(1, len(texts) // max(1, args.warmup))
    warm_rows = []
    for i in range(args.warmup):
        msg_index = (i * step) % len(texts)
        text = texts[msg_index]
        t = _time.perf_counter()
        spans = call(text)
        warm_rows.append({"call_index": i + 1, "msg_index": msg_index,
                          "chars": len(text), "spans": len(spans),
                          "detect_ms": (_time.perf_counter() - t) * 1000,
                          "phase": "warmup"})
    rss_warmup = pc.rss_mb()
    cur_warmup = pc.current_rss_mb()
    warm_end_wall = _time.time()
    warm_ms = [row["detect_ms"] for row in warm_rows]

    # ---- 6) N timed calls, one corpus message each, in file order ----------
    timed_rows = []
    base = 0
    t_loop = _time.perf_counter()
    for i in range(args.n):
        msg_index = (base + i) % len(texts)
        text = texts[msg_index]
        t = _time.perf_counter()
        spans = call(text)
        timed_rows.append({"call_index": base + i, "msg_index": msg_index,
                           "chars": len(text), "spans": len(spans),
                           "detect_ms": (_time.perf_counter() - t) * 1000,
                           "phase": "timed"})
    elapsed = _time.perf_counter() - t_loop
    rss_n = pc.rss_mb()
    cur_n = pc.current_rss_mb()

    samples = [row["detect_ms"] for row in timed_rows]
    meta = {
        "arm": args.arm,
        "repeat": args.repeat,
        "arm_kind": "product_in_process" if args.arm == "FULL" else "diagnostic_ablation",
        "cold_start_ms": round(cold_start_ms, 3),
        "cold_start_origin": cold_origin,
        "cold_in_process_ms": round(cold_in_process_ms, 3),
        "interpreter_startup_ms": round(interpreter_startup_ms, 3),
        "p50": round(pc.pct(samples, 0.50), 4),
        "p95": round(pc.pct(samples, 0.95), 4),
        "p99": round(pc.pct(samples, 0.99), 4),
        "mean": round(statistics.mean(samples), 4),
        "stdev": round(statistics.stdev(samples), 4) if len(samples) > 1 else None,
        "min": round(min(samples), 4),
        "max": round(max(samples), 4),
        "rss_after_modules_mb": phases["rss_after_modules"]["mb"],
        "rss_after_import_mb": phases["rss_after_import"]["mb"],
        "rss_after_load_mb": phases["rss_after_load"]["mb"],
        "rss_after_warmup_mb": rss_warmup["mb"],
        "rss_after_n_mb": rss_n["mb"],
        "cur_rss_after_modules_mb": phases["cur_after_modules"],
        "cur_rss_after_import_mb": phases["cur_after_import"],
        "cur_rss_after_load_mb": phases["cur_after_load"],
        "cur_rss_after_warmup_mb": cur_warmup,
        "cur_rss_after_n_mb": cur_n,
        "rss_units_note": rss_n["kind"],
        "time_to_warm_ms": round((warm_end_wall - spawn_wall) * 1000, 3),
        "throughput_msg_s": round(args.n / elapsed, 2),
        "timed_loop_s": round(elapsed, 3),
        "model_bytes": pc.model_bytes_total(),
        "corpus_sha256": corpus_sha,
        "module_manifest_sha256": pc.manifest_sha256(pc.module_manifest()),
        "n": args.n,
        "warmup": args.warmup,
        "warmup_selection": f"spread: every {step}-th corpus message",
        "warmup_max_ms": round(max(warm_ms), 4),
        "warmup_mean_ms": round(statistics.mean(warm_ms), 4),
        "warmup_sum_ms": round(sum(warm_ms), 3),
        "corpus_messages": len(messages),
        "unique_timed_texts": len({row["msg_index"] for row in timed_rows}),
        "percentile_definition": pc.PCT_DEFINITION,
        "import_ms": round(phases["import_ms"], 1),
        "bundle_load_ms": round(phases["bundle_load_ms"], 1),
        "model_load_ms": round(phases["model_load_ms"], 1),
        "bundle_version": phases["bundle_version"],
        "controls": controls,
        "python": sys.version,
        "platform": platform.platform(),
        "executable": sys.executable,
        "prespawn": os.environ.get("PERF_CHILD") == "1",
    }

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        handle.write(f"# arm={args.arm} repeat={args.repeat} n={args.n} "
                     f"warmup={args.warmup}\n")
        handle.write(f"# corpus_sha256={corpus_sha}\n")
        handle.write(f"# module_manifest_sha256={meta['module_manifest_sha256']}\n")
        handle.write(f"# percentile_definition={pc.PCT_DEFINITION}\n")
        handle.write(f"# rows: phase cold|warmup|timed; only phase=timed enters "
                     f"p50/p95/p99/mean/stdev/throughput\n")
        handle.write("call_index\tmsg_index\tchars\tspans\tdetect_ms\tphase\n")
        for row in [cold_call, *warm_rows, *timed_rows]:
            handle.write(f"{row['call_index']}\t{row['msg_index']}\t{row['chars']}\t"
                         f"{row['spans']}\t{row['detect_ms']:.4f}\t{row['phase']}\n")
    meta_out = out.with_suffix(".meta.json")
    meta_out.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")

    print(f"[{args.arm} run{args.repeat}] n={args.n} corpus={len(messages)} msgs "
          f"({meta['unique_timed_texts']} unique timed)")
    print(f"  cold_start_ms={meta['cold_start_ms']} ({cold_origin}) "
          f"in_process={meta['cold_in_process_ms']} ms "
          f"interpreter_startup={meta['interpreter_startup_ms']} ms")
    print(f"  p50={meta['p50']} p95={meta['p95']} p99={meta['p99']} "
          f"mean={meta['mean']} stdev={meta['stdev']} ms")
    print(f"  rss modules/import/load/warmup/after_n = "
          f"{meta['rss_after_modules_mb']}/{meta['rss_after_import_mb']}/"
          f"{meta['rss_after_load_mb']}/{meta['rss_after_warmup_mb']}/"
          f"{meta['rss_after_n_mb']} MiB")
    print(f"  warmup (discarded, {meta['warmup_selection']}): "
          f"max={meta['warmup_max_ms']} mean={meta['warmup_mean_ms']} ms  "
          f"time_to_warm={meta['time_to_warm_ms']} ms")
    print(f"  current rss modules/import/load/warmup/after_n = "
          f"{meta['cur_rss_after_modules_mb']}/{meta['cur_rss_after_import_mb']}/"
          f"{meta['cur_rss_after_load_mb']}/{meta['cur_rss_after_warmup_mb']}/"
          f"{meta['cur_rss_after_n_mb']} MiB  (peak column above)")
    print(f"  throughput={meta['throughput_msg_s']} msg/s  "
          f"model_bytes={meta['model_bytes']}  bundle={meta['bundle_version']}")
    print(f"  controls: positive={controls['positive_spans']} spans "
          f"{controls['positive_types']} negative={controls['negative_spans']}")
    print(f"  -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
