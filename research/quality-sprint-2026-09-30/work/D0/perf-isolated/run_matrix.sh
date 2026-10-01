#!/bin/sh
# Run the bounded O-DETECT matrix: 2 arms x 3 independent processes, sequential.
#
# RUNBOOK-PERF §0.5: one process per arm, sequential — Python caches the natasha
# model on first use, so two arms in one process would contaminate the second
# one's cold start and RSS. This script therefore never runs anything in
# parallel, and it is the ONLY thing that starts measurement processes.
#
# It wraps each run in `/usr/bin/time -l` so the process-level peak RSS is
# captured independently of `resource.getrusage` inside the child (macOS reports
# it in bytes; Linux would need `-v`).
#
# Usage: sh run_matrix.sh [n] [warmup] [repeats]
set -u
N=${1:-1000}
WARM=${2:-50}
REPEATS=${3:-3}

HERE=$(cd "$(dirname "$0")" && pwd)
PROTO=$(cd "$HERE/../../../../../prototype" && pwd)
PY="$PROTO/.venv/bin/python"
CORPUS="$HERE/corpus.jsonl"
RAW="$HERE/raw"
LOGS="$HERE/logs"
mkdir -p "$RAW" "$LOGS"

echo "== run_matrix: n=$N warmup=$WARM repeats=$REPEATS =="
echo "== python: $PY =="
echo "== command shape: cd $PROTO && PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -l $PY $HERE/perf_one_arm.py --arm <ARM> --corpus $CORPUS --n $N --warmup $WARM --repeat <k> --out $RAW/<ARM>-run<k>.tsv =="
date -u +"== start %Y-%m-%dT%H:%M:%SZ =="
uptime
ps -Ao "%cpu=,pid=,command=" -r | head -6

FAIL=0
for ARM in FULL NER_ONLY; do
  for K in $(seq 1 "$REPEATS"); do
    OUT="$RAW/$ARM-run$K.tsv"
    LOG="$LOGS/run-$ARM-run$K.log"
    echo "--- $ARM run$K -> $OUT"
    ( cd "$PROTO" && PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -l \
        "$PY" "$HERE/perf_one_arm.py" --arm "$ARM" --corpus "$CORPUS" \
        --n "$N" --warmup "$WARM" --repeat "$K" --out "$OUT" ) >"$LOG" 2>&1
    CODE=$?
    echo "--- exit=$CODE"
    grep -E "^(maximum resident set size|real|user|sys)" "$LOG" || true
    [ "$CODE" -ne 0 ] && FAIL=1
  done
done

date -u +"== end %Y-%m-%dT%H:%M:%SZ =="
uptime
echo "== run_matrix exit=$FAIL (0 = every measurement process exited 0) =="
exit "$FAIL"
