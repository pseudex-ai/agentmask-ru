#!/bin/sh
# Obscura sidecar entrypoint — N independent worker processes, one shared port.
#
# Real CPU parallelism comes from PROCESSES, not threads: pymorphy3 holds the GIL
# during morphology, so N threads in one process still serialize on one core.
#
# The fan-out is HERE, in shell, rather than in `uvicorn --workers N`, because a
# Nuitka-compiled binary cannot use uvicorn's worker manager (frozen executables
# have no working spawn/forkserver on Unix). Each worker binds its own
# SO_REUSEPORT socket to the same port and the kernel balances between them —
# see serve_main.py.
#
# MEMORY/THROUGHPUT TRADEOFF (measured ~300 MB resident per worker for the model
# stack): pick OBSCURA_WORKERS so N*300 MB fits the container memory limit with
# headroom, and N <= vCPU count.
#
# Each worker LEASES ITS OWN BUNDLE: its X25519 keypair never leaves its memory,
# so there is nothing to share and no IPC. A worker that cannot lease exits on
# its own; the supervisor below takes the whole container down with it, because a
# half-licensed container silently serving from two of eight workers is worse
# than a container that is plainly down.
#
# The per-worker MaskCache is not shared — that's fine: the persistent SQLite
# Vault + audit ARE shared (mounted volume), so tokens stay consistent and
# reversible across all workers.

set -e

if [ -n "$OBSCURA_WORKERS" ]; then
    WORKERS="$OBSCURA_WORKERS"
else
    WORKERS="$(nproc 2>/dev/null || echo 1)"
fi

# One id per CONTAINER, so the licensing server can tell "eight workers of one
# deployment" from "eight deployments".
if [ -z "$OBSCURA_INSTANCE_ID" ]; then
    OBSCURA_INSTANCE_ID="$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    export OBSCURA_INSTANCE_ID
fi

echo "obscura: starting ${WORKERS} worker(s), instance ${OBSCURA_INSTANCE_ID}"

pids=""
for i in $(seq 1 "${WORKERS}"); do
    ${OBSCURA_SERVE_CMD:-./obscura-serve} &
    pids="$pids $!"
done

# Any worker exiting takes the container down: exiting is how a worker reports
# "I have no valid licence", and that verdict applies to all of them.
terminate() {
    for pid in $pids; do kill "$pid" 2>/dev/null || true; done
    wait 2>/dev/null || true
}
trap terminate INT TERM

# Polled rather than `wait -n`: `wait -n || wait` swallowed the failing worker's
# status (the `||` fires on the very non-zero we wanted to report) and the
# container exited 0 while its only worker had died of a licensing error —
# which reads to any orchestrator as a clean shutdown. The exit code IS the
# signal here, so it is taken from the specific child that died.
while :; do
    for pid in $pids; do
        if ! kill -0 "$pid" 2>/dev/null; then
            status=0
            wait "$pid" || status=$?
            echo "obscura: worker ${pid} exited with status ${status} — stopping the container"
            terminate
            exit "${status}"
        fi
    done
    sleep 1
done
