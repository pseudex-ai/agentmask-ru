#!/bin/sh
# S1 revision-2 runner — bounded in-memory probes only. No provider, no network.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
PROTO="$ROOT/prototype"
PY="$PROTO/.venv/bin/python"

echo "# S1 revision-2 run $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "# cwd=$PROTO"
echo "# interpreter=$PY"
echo "# python=$($PY -V 2>&1)"
echo "# git HEAD=$(git -C "$ROOT" rev-parse HEAD)"
echo "# command: $PY s1_probes_v2.py   (exit = number of VIOLATED properties)"
echo "# --- probe run ---"
cd "$PROTO" || exit 2
PYTHONDONTWRITEBYTECODE=1 "$PY" "$HERE/s1_probes_v2.py" \
    > "$HERE/tmp/probes_v2.stdout" 2> "$HERE/tmp/probes_v2.stderr"
EXIT=$?
cat "$HERE/tmp/probes_v2.stdout"
echo "EXIT=$EXIT"
echo "EXPECTED_RED=4"
echo "# stderr bytes: $(wc -c < "$HERE/tmp/probes_v2.stderr")"
echo "# --- output hashes ---"
shasum -a 256 "$HERE/s1_probes_v2.py" "$HERE/tmp/probes_v2.stdout" 2>/dev/null \
    || sha256sum "$HERE/s1_probes_v2.py" "$HERE/tmp/probes_v2.stdout"
echo "# --- preserved originals (must be unchanged by this run) ---"
shasum -a 256 "$ROOT/research/quality-sprint-2026-09-30/work/S1/s1_probes.py" \
              "$ROOT/research/quality-sprint-2026-09-30/work/S1/SPEC.md" \
              "$ROOT/research/quality-sprint-2026-09-30/work/S1/GATE.json" \
              "$ROOT/research/quality-sprint-2026-09-30/work/S1/OWNER-QUESTIONS.md"
exit 0
