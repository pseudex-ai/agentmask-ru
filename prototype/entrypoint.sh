#!/bin/sh
# Obscura sidecar entrypoint — env-configurable uvicorn worker count.
#
# Real CPU parallelism comes from PROCESSES, not threads: pymorphy3 holds the GIL
# during morphology, so N threads in one process still serialize on one core. Each
# uvicorn worker is a separate process with its own event loop AND its own copy of
# the pymorphy3 + natasha models.
#
# MEMORY/THROUGHPUT TRADEOFF (measured ~300 MB resident per worker for the model
# stack on python:3.12-slim):
#   workers=1  -> ~300 MB, 1 core   (the old default; one in-flight mask serializes
#                                     everything -> false-unhealthy under load)
#   workers=N  -> ~N*300 MB, N cores (linear RAM cost, linear CPU parallelism)
# Pick OBSCURA_WORKERS so N*300 MB fits the container memory limit with headroom,
# and N <= vCPU count. Default: number of CPUs (capped), which is the standard
# "one worker per core" rule for CPU-bound services.
#
# The per-worker in-process MaskCache is NOT shared across workers — that's fine:
# the persistent SQLite Vault + audit ARE shared (mounted volume), so tokens stay
# consistent and reversible across all workers; the cache only avoids recomputation
# and each worker warms its own independently.

set -e

if [ -n "$OBSCURA_WORKERS" ]; then
    WORKERS="$OBSCURA_WORKERS"
else
    # Default to CPU count (one worker per core), falling back to 1.
    WORKERS="$(python -c 'import os; print(os.cpu_count() or 1)')"
fi

echo "obscura: starting uvicorn with ${WORKERS} worker(s)"
exec uvicorn obscura.service:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${WORKERS}"
