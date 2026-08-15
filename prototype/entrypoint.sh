#!/bin/sh
# Pseudex sidecar entrypoint — N independent worker processes, one shared port.
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
# stack): pick PSEUDEX_WORKERS so N*300 MB fits the container memory limit with
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

if [ -n "$PSEUDEX_WORKERS" ]; then
    WORKERS="$PSEUDEX_WORKERS"
else
    WORKERS="$(nproc 2>/dev/null || echo 1)"
fi

# One id per CONTAINER, so the licensing server can tell "eight workers of one
# deployment" from "eight deployments".
if [ -z "$PSEUDEX_INSTANCE_ID" ]; then
    PSEUDEX_INSTANCE_ID="$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    export PSEUDEX_INSTANCE_ID
fi

# The operator token gates /reveal and the whole log/statistics surface. It MUST
# be generated here, once, and inherited: each worker generating its own would
# mean N different valid tokens for one port, and SO_REUSEPORT would hand the
# interface a different worker on the next connection — the log would work and
# then 401 at random.
if [ -z "$PSEUDEX_ADMIN_TOKEN" ]; then
    PSEUDEX_ADMIN_TOKEN="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    export PSEUDEX_ADMIN_TOKEN
fi
# Credential the customer's gateway presents on /mask, /unmask and /spans.
# Generated here for the same reason as the admin token: per-process values
# behind one SO_REUSEPORT port would reject the gateway at random.
if [ -z "$PSEUDEX_GATEWAY_TOKEN" ]; then
    PSEUDEX_GATEWAY_TOKEN="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    export PSEUDEX_GATEWAY_TOKEN
fi
# Sign-in token for the interface. Generated here rather than in the UI process
# so it survives a UI restart: an operator who followed the link from the log
# should not be locked out because that process was restarted at 03:00.
if [ -z "$PSEUDEX_UI_TOKEN" ]; then
    PSEUDEX_UI_TOKEN="$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    export PSEUDEX_UI_TOKEN
fi

echo "pseudex: starting ${WORKERS} worker(s), instance ${PSEUDEX_INSTANCE_ID}"
echo ""
echo "    ключ шлюза (Authorization: Bearer …) для /mask, /unmask, /spans:"
echo "    ${PSEUDEX_GATEWAY_TOKEN}"
echo ""

pids=""
for i in $(seq 1 "${WORKERS}"); do
    ${PSEUDEX_SERVE_CMD:-./pseudex-serve} &
    pids="$pids $!"
done

# The interface is supervised separately and deliberately does NOT join `pids`.
# A worker exiting means "no valid licence" and must stop the container; the
# interface failing means one screen is unavailable while masking is fine, and
# taking a working gateway down over it would be the wrong trade. It is
# restarted instead — and its restart is exactly the moment the operator needs
# it, since "движок не отвечает" is a state only the interface can report.
ui_pid=""
if [ "${PSEUDEX_UI:-1}" = "1" ]; then
    (
        while :; do
            PSEUDEX_ROLE=ui ${PSEUDEX_SERVE_CMD:-./pseudex-serve} || true
            echo "pseudex: local interface exited — restarting in 3s"
            sleep 3
        done
    ) &
    ui_pid=$!
fi

# Any worker exiting takes the container down: exiting is how a worker reports
# "I have no valid licence", and that verdict applies to all of them.
terminate() {
    for pid in $pids; do kill "$pid" 2>/dev/null || true; done
    # The supervisor subshell is killed first, or it would helpfully restart the
    # interface while the container is on its way down.
    [ -n "$ui_pid" ] && kill "$ui_pid" 2>/dev/null || true
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
            echo "pseudex: worker ${pid} exited with status ${status} — stopping the container"
            terminate
            exit "${status}"
        fi
    done
    sleep 1
done
