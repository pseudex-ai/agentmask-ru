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
# MEMORY/THROUGHPUT TRADEOFF (measured ~350 MB resident per worker for the model
# stack): N*350 MB has to fit the container's memory limit with headroom, and
# N <= vCPU count. That is no longer advice — `PSEUDEX_ROLE=preflight` below
# does the arithmetic before the fan-out and refuses or lowers N, because a
# comment cannot stop an OOM kill and 137 names neither memory nor us.
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

# ONE-SHOT ROLES RUN ONCE AND EXIT. They must be handled before anything below,
# because everything below assumes a SERVER: it fans out N copies of the binary
# and supervises them.
#
# Without this, `docker run -e PSEUDEX_ROLE=rekey` started ten rotations of the
# same volume at once. The lock made the outcome correct — one rotated, the rest
# found the file already on the new key — but each loser reported "ТОМ
# РАЗЪЕХАЛСЯ: старый ключ НЕ выключайте", which is the most frightening sentence
# this product can print, on a rotation that had in fact just succeeded. An
# operator reading that would stop and call us.
#
# `exec`, so the role's exit code is the container's: the probe's non-zero is
# what a healthcheck and a script read.
#
# `preflight` СТОИТ ЗДЕСЬ ЖЕ, хотя ниже этот же скрипт вызывает её сам: без
# строки в этом списке `docker run -e PSEUDEX_ROLE=preflight` уходил дальше по
# файлу, печатал ключ шлюза, «запускал» N процессов, каждый из которых просто
# печатал число и выходил нулём, — и контейнер выходил нулём тоже. Роль,
# объявленная в документации, обязана быть одноразовой на самом деле.
# Рекурсии нет: ниже вызывается БИНАРНИК, а не этот скрипт.
case "${PSEUDEX_ROLE:-sidecar}" in
    preflight|probe|rekey|decrypt)
        exec ${PSEUDEX_SERVE_CMD:-./pseudex-serve}
        ;;
esac

# СКОЛЬКО ВОРКЕРОВ ВЛЕЗАЕТ — СПРАШИВАЕТСЯ ДО ТОГО, КАК ЗАПУЩЕН ХОТЬ ОДИН.
#
# Выше стоял комментарий «подберите PSEUDEX_WORKERS так, чтобы N*300 МБ влезли в
# лимит контейнера», и комментарий не умеет отказывать. Вместо отказа
# происходило вот что: фан-аут стартовал, OOM-killer забирал того воркера,
# который последним попросил страницу, супервизор ниже видел ушедшего ребёнка и
# ронял контейнер со статусом 137 — числом, которое не называет ни память, ни
# нас. Всё это известно ЗАРАНЕЕ: лимит лежит в файле, цена воркера измерена,
# арифметика — одно деление.
#
# Роль вызывается ровно как `probe` ниже, и по тому же контракту: единственная
# строка stdout — число воркеров, всё человеческое — в stderr, ненулевой код —
# отказ. Причина уже напечатана ролью, поэтому здесь только вывод.
if ! WORKERS="$(PSEUDEX_ROLE=preflight ${PSEUDEX_SERVE_CMD:-./pseudex-serve})"; then
    echo ""
    echo "pseudex: контейнер остановлен — под запрошенные воркеры не хватает памяти."
    echo "         Строка «pseudex preflight:» выше говорит, сколько дать или сколько просить."
    exit 4
fi

# ЧИСЛО ПРОВЕРЯЕТСЯ, А НЕ ПРИНИМАЕТСЯ НА ВЕРУ, и это нашёл негативный прогон
# собственной проверки. Пустой ответ (роль вышла нулём, но ничего не напечатала)
# превращает цикл ниже в `seq 1 ""`, который не запускает НИ ОДНОГО воркера, —
# а супервизор в конце файла обходит пустой список и крутится вечно. Контейнер
# при этом «запущен», отвечает на `docker ps`, и не делает ничего. Это худший из
# отказов: он не виден ни одним способом, каким смотрят на контейнер.
case "$WORKERS" in
    ''|*[!0-9]*)
        echo "pseudex: предполёт вернул «${WORKERS}» вместо числа воркеров — это наша ошибка, а не ваша конфигурация."
        exit 4
        ;;
esac
if [ "$WORKERS" -lt 1 ]; then
    echo "pseudex: предполёт вернул ${WORKERS} воркеров — запускать нечего."
    exit 4
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

# The volume is checked ONCE, here, before any worker opens it: a key that does
# not open the vault would otherwise be reported N times — once per worker,
# interleaved, in a log the operator reads top-down — and the container would
# exit on whichever worker lost the race, with the same message buried N deep.
#
# It does NOT migrate and does NOT create the key. It used to do the second, and
# that was a defect rather than a service: the same role is the command we hand
# customers to check a live volume, and run without the key variables it wrote a
# new key beside their data and then reported every store unopenable with it. On
# a fresh volume the FIRST WORKER now creates the key under `O_EXCL` and the rest
# read its file — which they already had to be able to do, since `uvicorn
# pseudex.service:app` is a supported launch shape that never runs this script
# (CLAUDE.md, deployment shape B).
#
# The plaintext-to-encrypted conversion stays inside the connection factory under
# its own flock for the same reason: a migration that only happened here would be
# a migration half the deployments never get.
if ! PSEUDEX_ROLE=probe ${PSEUDEX_SERVE_CMD:-./pseudex-serve}; then
    echo ""
    echo "pseudex: том не открывается текущим ключом — контейнер остановлен."
    echo "         PSEUDEX_ROLE=probe выше показывает, какой файл и почему."
    exit 3
fi
echo ""

echo "pseudex: starting ${WORKERS} worker(s), instance ${PSEUDEX_INSTANCE_ID}"
echo ""
if [ "${PSEUDEX_ROLE:-sidecar}" = "proxy" ]; then
    echo "    ключ шлюза (Authorization: Bearer …) для /spans и /reveal:"
    echo "    (в режиме proxy маскирование идёт внутри /v1/chat/completions —"
    echo "     отдельных /mask и /unmask здесь нет)"
else
    echo "    ключ шлюза (Authorization: Bearer …) для /mask, /unmask, /spans:"
fi
echo "    ${PSEUDEX_GATEWAY_TOKEN}"
echo ""

pids=""
for i in $(seq 1 "${WORKERS}"); do
    ${PSEUDEX_SERVE_CMD:-./pseudex-serve} &
    pids="$pids $!"
done

# ПУСТОЙ СПИСОК — ЭТО ОТКАЗ, А НЕ СОСТОЯНИЕ ПОКОЯ. Супервизор внизу обходит
# `pids` и спит; по пустому списку он обходит ничего и спит вечно, ничего не
# напечатав. Проверка выше делает это недостижимым, и она же однажды перестанет
# быть верной — поэтому второй рубеж стоит здесь, у самого цикла.
if [ -z "$pids" ]; then
    echo "pseudex: не запущено ни одного воркера — контейнер остановлен."
    exit 4
fi

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
