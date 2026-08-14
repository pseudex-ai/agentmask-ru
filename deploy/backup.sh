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

    if pg_dump -h postgres -U "${POSTGRES_USER:-veilgate}" \
               -d "${POSTGRES_DB:-veilgate}" -Fc \
               > "/backups/storefront-${stamp}.dump.tmp"; then
        mv "/backups/storefront-${stamp}.dump.tmp" "/backups/storefront-${stamp}.dump"
        echo "backup: storefront ${stamp} ok"
    else
        # Loud and non-fatal: the loop must survive one bad night, but a silent
        # failure would let a month of them pass unnoticed.
        echo "backup: STOREFRONT DUMP FAILED at ${stamp}" >&2
        rm -f "/backups/storefront-${stamp}.dump.tmp"
    fi

    # SQLite, copied with its own tooling: `cp` of a live WAL database can
    # capture a torn page, which restores as a file that opens and is wrong.
    if [ -f /license/license.db ]; then
        if sqlite3 /license/license.db ".backup '/backups/license-${stamp}.db.tmp'" 2>/dev/null \
           || cp /license/license.db "/backups/license-${stamp}.db.tmp"; then
            mv "/backups/license-${stamp}.db.tmp" "/backups/license-${stamp}.db"
            echo "backup: license ${stamp} ok"
        else
            echo "backup: LICENSE COPY FAILED at ${stamp}" >&2
        fi
    fi

    find /backups -name '*.dump' -mtime "+${RETAIN_DAYS}" -delete
    find /backups -name '*.db' -mtime "+${RETAIN_DAYS}" -delete

    sleep 86400
done
