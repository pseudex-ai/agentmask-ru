# RUNBOOK — controlled detector resource experiment (for `O-DETECT`)

Purpose: produce the **measured CPU/RAM/latency** numbers that
[SPRINT-PLAN §7](<../SPRINT-PLAN.md#L174>) and
[REMAINING-DECISIONS block 4](<../REMAINING-DECISIONS.md#L31-L32>) require before
any mechanism is adopted. D0 deliberately did **not** produce them: its run was a
single exploratory pass on a host shared with other sprint tasks, and the same
harness gave 12.35 ms/text and 7.58 ms/text for the same arm on two runs.

This runbook is written so that a different agent can execute it and get the same
kind of number. Nothing here authorises a download, an install, a provider call,
or an engine patch.

## 0. Preconditions (all must hold, recorded in the run's `env.json`)

1. **Isolation.** No other NER/container/benchmark job is running. SPRINT-PLAN §5
   allows one resource-heavy test at a time; a shared host makes every number
   exploratory. Record `uptime`, load average and whether other sprint tasks were
   active.
2. **Frozen inputs.** Record before the first measurement: git HEAD, the hashes of
   every `prototype/pseudex/*.py` and `prototype/licensing/*.py` module, the
   in-memory bundle identity (`build_plaintext()` → version/bytes/sha256), the
   model-weight hashes, and the corpus file hash. If any of them changes mid-run,
   the run is void.
3. **Fixed corpus, not the holdout.** Use a frozen file in the run's own folder:
   300–1000 messages, deterministic order, mixture of typed KV, free prose,
   chat/sloppy registers and (licence-permitting) real-speech utterances whose
   text is **not** copied into the artifacts. The 359-ID holdout stays unread;
   the paid run directory stays unread.
4. **No new software.** If a candidate is not runnable with what is installed,
   the experiment stops and asks the owner for an acquisition decision — running
   it is not authorised by this runbook.
5. **One process per arm, sequential.** Python caches the natasha model on first
   use; two arms in one process would contaminate the second one's cold-start and
   RSS numbers.

## 1. What to measure per arm

| Metric | Definition | How |
|---|---|---|
| cold start | process start → first successful `detect()` return | `time.perf_counter()` around first call, after imports |
| p50 / p95 / p99 per-message detect | wall time of `Detector.detect(text)` (or the candidate's equivalent) | 50 warm-up messages discarded, then N ≥ 1000 timed calls, one text per call |
| mean / stdev | over the same N | `statistics` |
| RSS after import / after model load / after warm-up / after N | peak resident set of the process | `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss` at each point (macOS: bytes; Linux: KiB) and `/usr/bin/time -l` (macOS) or `/usr/bin/time -v` (Linux) for the process peak |
| throughput, 1 worker | N / elapsed | same loop |
| model bytes on disk | sum of the weight files the arm loads | precomputed hash table from [out/source-hashes.json](out/source-hashes.json) plus the candidate's files |
| image-size delta | only for a candidate that would ship | `docker build` + `docker image inspect` — **needs an owner GO**, out of scope here |
| repeats | k = 5 independent processes per arm | report per-repeat values, plus p50 of the p50s and the spread; never average away the spread |

If the question is the **G9 runtime contract** (HTTP gateway, streaming, workers),
repeat the same measurement through the real service (`uvicorn pseudex.service:app`,
`/mask` with `PSEUDEX_GATEWAY_TOKEN`) in a **separate** phase — the in-process
number is not a compiled-production proof.

## 2. Exact procedure

```bash
# 0) isolation: verify nothing heavy is running, then record it
uptime; ps -Ao %cpu,comm | sort -nr | head

# 1) freeze the corpus and write env.json (HEAD, module hashes, bundle id,
#    corpus sha256, python/libs) — in the new run's own folder, under work/<PERF-ID>/

# 2) per arm, in its own process:
cd prototype
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  ../research/quality-sprint-2026-09-30/work/<PERF-ID>/perf_one_arm.py \
  --arm FULL --corpus ../research/quality-sprint-2026-09-30/work/<PERF-ID>/corpus.jsonl \
  --n 1000 --out ../research/quality-sprint-2026-09-30/work/<PERF-ID>/raw/FULL-run1.tsv

# 3) repeat step 2 five times per arm (run1..run5), then summarise:
PYTHONDONTWRITEBYTECODE=1 python3 \
  ../research/quality-sprint-2026-09-30/work/<PERF-ID>/summarise.py \
  --raw-dir ../research/quality-sprint-2026-09-30/work/<PERF-ID>/raw \
  --out ../research/quality-sprint-2026-09-30/work/<PERF-ID>/summary.json
```

`perf_one_arm.py` should be a copy of the pattern in
[prototype/profile_latency.py](</prototype/profile_latency.py>) — which already
implements warm-up, p50/p95 and a `Vault(":memory:")` round trip — but **copied
into the new scope**, because:

- that script reads `holdout.json`, which does not exist in this workspace and
  must not be manufactured (it measures a *meter*, not a mechanism);
- editing a shared benchmark file would collide with the single benchmark writer
  rule (SPRINT-PLAN §5, §6 M1c).

Same-file pattern for the report:

```
arm, repeat, cold_start_ms, p50, p95, p99, mean, stdev, rss_after_import_mb,
rss_after_load_mb, rss_after_warmup_mb, rss_after_n_mb, throughput_msg_s,
model_bytes, corpus_sha256, module_manifest_sha256
```

## 3. Reporting rules (non-negotiable, from the sprint contract)

- A number measured on a host with other active work is labelled **exploratory**
  and must not enter an admission budget.
- p50/p95 come from ≥ 1000 samples in ≥ 5 processes. A single run's p50 is not a
  p50.
- Arms must be measured with the same corpus, same N, same warm-up and same
  concurrency; an arm measured under different conditions is not comparable and
  is not put in the same table.
- No candidate is described as better before both quality (harness on approved
  gold) and cost (this runbook) exist; the two are reported as separate axes.
- Material resource regression is put to the owner **before** adoption, with the
  current baseline numbers next to it: ~350 MB resident per worker
  ([preflight.py:19,33](</prototype/pseudex/preflight.py#L19>)), image < 1.5 GB
  and cold start < 20 s (P8, [docs/tz-license-packaging.md:931](</docs/tz-license-packaging.md#L931>)),
  lease payload 1 524 582 B.
- If the candidate cannot be run without installing/downloading something, the
  experiment reports `NOT_MEASURED` and asks the owner; it does not improvise.

## 4. Output of this experiment, and where it goes

1. `raw/<arm>-run<k>.tsv` — one row per message.
2. `summary.json` — per-arm per-repeat metrics, spread, environment, hashes.
3. `GATE.json` with status `PASS` only for "measurement executed reproducibly";
   the architecture question itself stays `O-DETECT = OWNER_PENDING` until the
   owner answers it.
4. The summary feeds the `O-DETECT` question together with the quality table from
   a D0-style harness extended with the candidate arm, on gold approved through
   `O-DATA`. Neither table alone answers the question.
