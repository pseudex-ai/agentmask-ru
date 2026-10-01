#!/bin/sh
# S1 runner — executed from /Users/igor/Projects/Obscura-hop-audit.
# Writes only inside work/S1. Read-only against prototype/, licensing/ and git.
#
# Usage:  sh research/quality-sprint-2026-09-30/work/S1/run-s1.sh
#
# Exit code is the probe's own exit code (number of VIOLATED properties); the
# expected value for the pinned revision is 4, i.e. this is an intentional RED.
set -u
ROOT=/Users/igor/Projects/Obscura-hop-audit
S1="$ROOT/research/quality-sprint-2026-09-30/work/S1"
PY="$ROOT/prototype/.venv/bin/python"
cd "$ROOT/prototype" || exit 90

{
  echo "# s1 run $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# cwd=$(pwd)"
  echo "# interpreter=$PY"
  echo "# python=$("$PY" -V 2>&1)"
  echo "# git HEAD=$(git -C "$ROOT" rev-parse HEAD)"
  echo "# product diff 0bfda236..HEAD (prototype licensing storefront deploy wiki) ="
  git -C "$ROOT" diff --stat 0bfda2363ef1a1d552e2ac093129b1026a86ad68..HEAD -- \
      prototype licensing storefront deploy wiki
  echo "# tracked worktree status (prototype/licensing only; must stay unchanged by this run) ="
  git -C "$ROOT" status --porcelain -- prototype licensing
  echo "# --- probe run ---"
} > "$S1/RED.log" 2>&1

PYTHONDONTWRITEBYTECODE=1 "$PY" "$S1/s1_probes.py" >> "$S1/RED.log" 2>&1
RC=$?
{
  echo "EXIT=$RC"
  echo "EXPECTED_RED=4"
  echo "# tracked worktree status after run (must equal the block above) ="
  git -C "$ROOT" status --porcelain -- prototype licensing
} >> "$S1/RED.log" 2>&1

# Determinism of the violated-property SET across three independent mints.
for n in 2 3; do
  PYTHONDONTWRITEBYTECODE=1 "$PY" "$S1/s1_probes.py" > "$S1/determinism-run$n.log" 2>&1
  echo "run$n EXIT=$?" >> "$S1/determinism-run$n.log"
done

# The observed mint is random per run; hash the captured state for this log.
{
  echo "fixture_spec_sha256=$(grep -m1 '^# fixture_spec_sha256=' "$S1/RED.log" | cut -d= -f2)"
  for f in RED.log determinism-run2.log determinism-run3.log; do
    echo "$f sha256=$(shasum -a 256 "$S1/$f" | cut -d' ' -f1)"
  done
} > "$S1/HASHES.txt"

exit $RC
