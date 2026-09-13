#!/bin/sh
# Nightly backups of both databases.
#
# The licensing database is the one that cannot be reconstructed: it holds every
# customer key. Losing it stops every deployment in the field, and no code
# change recovers that — so this runs in its own container with its own restart
# policy rather than as a cron job on a host somebody might rebuild.
#
# Restores are TESTED by the freshness check below refusing to be silent: a
# backup nobody verified is a backup that does not exist.
set -eu

RETAIN_DAYS="${RETAIN_DAYS:-30}"

while :; do
    stamp="$(date -u +%Y%m%dT%H%M%SZ)"

    if pg_dump -h postgres -U "${POSTGRES_USER:-pseudex}" \
               -d "${POSTGRES_DB:-pseudex}" -Fc \
               > "/backups/storefront-${stamp}.dump.tmp"; then
        # `set -e` KILLS THIS LOOP through the LAST command of a branch, and
        # only through that one. A bare `mv` here is exactly that: it fails, the
        # script exits, the container restarts, and the next round re-runs
        # pg_dump instead of logging and sleeping. Inside an `if` condition it
        # cannot — POSIX exempts the condition, and the failure gets a line.
        if mv "/backups/storefront-${stamp}.dump.tmp" \
              "/backups/storefront-${stamp}.dump"; then
            echo "backup: storefront ${stamp} ok"
        else
            echo "backup: STOREFRONT DUMP TAKEN BUT NOT PUBLISHED at ${stamp}" >&2
            rm -f "/backups/storefront-${stamp}.dump.tmp"
        fi
    else
        # Loud and non-fatal: the loop must survive one bad night, but a silent
        # failure would let a month of them pass unnoticed.
        echo "backup: STOREFRONT DUMP FAILED at ${stamp}" >&2
        rm -f "/backups/storefront-${stamp}.dump.tmp"
    fi

    # SQLite, copied with its own tooling: `cp` of a live WAL database can
    # capture a torn page, which restores as a file that opens and is wrong.
    #
    # THAT BRANCH HAD NEVER RUN. This container is `postgres:17-alpine`, which
    # ships no `sqlite3` at all, so every nightly copy since the first one has
    # silently taken the `cp` fallback the comment above exists to avoid — and
    # the watchdog only ever looks at file AGE, so a torn copy passes every
    # check we have. `apk add` is one line and makes the intended path the one
    # that actually happens.
    # THE MOUNT IS READ-WRITE, and `.backup` is why (compose.yml says it at the
    # mount). The licensing database is in WAL mode, SQLite needs to create the
    # `-shm` wal-index beside it to read one, and `-shm` is absent exactly when
    # the licensing container is stopped — so on `:ro` this branch failed on the
    # night the backup mattered most, and the watchdog only checks file age.
    if [ -f /license/license.db ]; then
        # `cp`-ВЕТКИ БОЛЬШЕ НЕТ, И ЭТО ГЛАВНОЕ ИЗМЕНЕНИЕ ЗДЕСЬ. Она стояла как
        # запасной путь на случай отсутствия `sqlite3` — и была ЕДИНСТВЕННЫМ
        # путём, потому что базовый образ его не нёс: каждая ночная копия
        # лицензионной базы бралась `cp` с живой WAL-базы и могла быть рваной,
        # а сторож смотрит только на возраст файла. Инструмент теперь внутри
        # образа (Dockerfile.backup), поэтому запасной путь не нужен: его
        # отсутствие — это отказ сборки, а не тихая порча ночной копии.
        if sqlite3 /license/license.db ".backup '/backups/license-${stamp}.db.tmp'" 2>/tmp/lic.err; then
            if mv "/backups/license-${stamp}.db.tmp" "/backups/license-${stamp}.db"; then
                echo "backup: license ${stamp} ok"
            else
                echo "backup: LICENSE COPY TAKEN BUT NOT PUBLISHED at ${stamp}" >&2
                rm -f "/backups/license-${stamp}.db.tmp"
            fi
        else
            # NOT a silent fallback to `cp`. `sqlite3` answers `file is not a
            # database` to an ENCRYPTED store as well as to a broken one, and
            # taking a `cp` instead would hand us a copy nobody can open while
            # the log said "ok". The licensing database is deliberately NOT
            # encrypted (licensing/Dockerfile says why); if this fires, that
            # changed, and the copy needs the key-aware path — the same one
            # `licensing.verify` uses.
            echo "backup: LICENSE COPY FAILED at ${stamp}: $(cat /tmp/lic.err 2>/dev/null)" >&2
            rm -f "/backups/license-${stamp}.db.tmp"
        fi
    fi

    # ── ВЫВОЗ С ХОСТА ──────────────────────────────────────────────────────
    #
    # ЗАЧЕМ. `/backups` лежит на том же диске той же машины, что и базы. Это
    # защищает от «уронили таблицу» и не защищает НИ ОТ ЧЕГО, что случается с
    # машиной: отказ диска, инцидент у провайдера, чужой root, собственная
    # ошибка в `docker volume rm`. Лицензионная база — единственное, чего не
    # пересобрать из кода: в ней ключи всех клиентов, и её потеря останавливает
    # каждую установку в поле. Копия, живущая рядом с оригиналом, резервной не
    # является.
    #
    # ХОСТУ ЗАПРЕЩЁН `DeleteObject` ПОЛИТИКОЙ БАКЕТА, и это свойство, ради
    # которого стоит терпеть неудобство. Шифровальщик первым делом стирает
    # бэкапы, а уже потом шифрует; ключ, которым нельзя удалять, делает это
    # невозможным. Поэтому `forget --prune` идёт НЕ ОТСЮДА, а из GitHub Actions
    # другим ключом — тем же движением, что и `restic check`.
    #
    # ОТСУТСТВИЕ НАСТРОЙКИ — НЕ АВАРИЯ. Хост без вывоза работает, просто хуже
    # защищён; цикл, делающий локальные копии, не должен падать из-за этого.
    if [ -n "${RESTIC_REPOSITORY:-}" ] && [ -n "${RESTIC_PASSWORD:-}" ]; then
        # `init` идемпотентен по факту существования репозитория: «уже есть» —
        # это нормальный ответ, а не ошибка, и отличать его надо по проверке, а
        # не по коду возврата, который одинаков для «есть» и «нет доступа».
        if ! restic cat config >/dev/null 2>&1; then
            restic init >/dev/null 2>&1 \
                || echo "backup: restic init не удался — вывоз не настроен" >&2
        fi
        # --host фиксирован: иначе имя контейнера попадёт в снапшот, и после
        # пересоздания стека `restic snapshots --host` перестанет находить
        # собственную историю.
        if restic backup /backups --host pseudex --tag nightly \
                --exclude '*.tmp' --exclude '*.age' \
                >/tmp/restic.out 2>&1; then
            echo "backup: вывезено в объектное хранилище ${stamp}"
            # ОТМЕТКА ДЛЯ СТОРОЖА — одна на всё: он отвечает на вопрос «вывоз
            # вообще работает», а не «какой именно файл уехал».
            date -u +%s > /backups/.last-offsite
        else
            # Громко и не фатально: локальные копии уже сделаны и целы.
            # Молчание здесь заметит сторож по устаревшей отметке.
            echo "backup: ВЫВОЗ НЕ УДАЛСЯ ${stamp}: $(tail -3 /tmp/restic.out)" >&2
        fi
    else
        echo "backup: вывоз не настроен (нет RESTIC_REPOSITORY/RESTIC_PASSWORD) —" \
             "копии остались ТОЛЬКО на этом хосте" >&2
    fi

    # `|| echo` for the same reason as the two `mv`s above: these are the last
    # commands before `sleep`, and under `set -e` a sweep that fails (an
    # /backups that did not mount) would take the loop down and lose the backups
    # over the cleanup of the backups.
    find /backups -name '*.dump' -mtime "+${RETAIN_DAYS}" -delete \
        || echo "backup: retention sweep failed at ${stamp}" >&2
    find /backups -name '*.db' -mtime "+${RETAIN_DAYS}" -delete \
        || echo "backup: retention sweep failed at ${stamp}" >&2

    sleep 86400
done
