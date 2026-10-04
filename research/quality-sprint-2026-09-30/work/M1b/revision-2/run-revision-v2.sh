#!/bin/sh
# M1b revision-2 runner — bounded offline controls only. No provider, no network.
# Usage: sh run-revision-v2.sh   (from anywhere; paths are derived)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
PROTO="$ROOT/prototype"
PY="$PROTO/.venv/bin/python"
RUN="$PROTO/bench/runs/2026-09-30/v5-sprint-v2-813"
EXCLUDED="$ROOT/research/hop-format-audit/runs/cc3a551f-a8a5-4c0d-b90b-d3db2b26858a.excluded.json"

echo "# M1b revision-2 run $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "# cwd=$PROTO"
echo "# interpreter=$PY"
echo "# python=$($PY -V 2>&1)"
echo "# git HEAD=$(git -C "$ROOT" rev-parse HEAD)"
echo "# probe1 command: $PY probe_canary_reader_v2.py --run <run> --out $HERE"
echo "# probe2 command: $PY probe_parity_replay_v2.py --run <run> --out $HERE/probe_parity_replay_v2.json --reason-source <excluded.json>"
echo "# --- probe 1 ---"
cd "$PROTO" || exit 2
PYTHONDONTWRITEBYTECODE=1 "$PY" "$HERE/probe_canary_reader_v2.py" --run "$RUN" --out "$HERE" \
    > "$HERE/tmp/probe_canary_v2.stdout" 2> "$HERE/tmp/probe_canary_v2.stderr"
echo "EXIT_CANARY=$?"
echo "# --- probe 2 ---"
PYTHONDONTWRITEBYTECODE=1 "$PY" "$HERE/probe_parity_replay_v2.py" --run "$RUN" \
    --out "$HERE/probe_parity_replay_v2.json" --reason-source "$EXCLUDED" \
    > "$HERE/tmp/probe_parity_v2.stdout" 2> "$HERE/tmp/probe_parity_v2.stderr"
echo "EXIT_PARITY=$?"
echo "# --- stderr tails (empty expected) ---"
wc -c "$HERE/tmp/probe_canary_v2.stderr" "$HERE/tmp/probe_parity_v2.stderr"
echo "# --- output hashes ---"
for f in probe_canary_reader_v2.py probe_parity_replay_v2.py probe_canary_reader_v2.json probe_parity_replay_v2.json; do
    shasum -a 256 "$HERE/$f" 2>/dev/null || sha256sum "$HERE/$f"
done
echo "# --- preserved originals (must be unchanged by this run) ---"
shasum -a 256 "$ROOT/research/quality-sprint-2026-09-30/work/M1b/probe_parity_replay.py" \
              "$ROOT/research/quality-sprint-2026-09-30/work/M1b/probe_canary_reader.py" \
              "$ROOT/research/quality-sprint-2026-09-30/work/M1b/SPEC.md" \
              "$ROOT/research/quality-sprint-2026-09-30/work/M1b/GATE.json"
