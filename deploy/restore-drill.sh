#!/bin/sh
# Учения: развернуть вчерашний бэкап и убедиться, что он живой.
#
# ЗАЧЕМ, ЕСЛИ СТОРОЖ УЖЕ СМОТРИТ ЗА СВЕЖЕСТЬЮ. Свежий файл и восстановимый
# файл — разные утверждения, и разница обнаруживается ровно один раз: когда
# восстанавливать уже надо. `backup.sh` говорит это прямым текстом — «бэкап,
# который никто не разворачивал, — это отсутствующий бэкап», — и до сих пор это
# была фраза, а не проверка.
#
# ЧТО ИМЕННО ПРОВЕРЯЕТСЯ. Не «файл читается», а «из него поднимается рабочая
# база с непустыми таблицами». Дамп, оборванный на середине, читается прекрасно
# и восстанавливается в пустоту.
#
# БОЕВОЕ НЕ ТРОГАЕТСЯ. Витрина разворачивается во временную базу рядом,
# лицензии — во временный файл. По окончании всё удаляется.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
BACKUPS="${PSEUDEX_BACKUP_DIR:-$HERE/backups}"
notify() { "$HERE/notify.sh" "$@" || true; }
fail() { notify crit "Учения по восстановлению ПРОВАЛЕНЫ" "$1"; exit 1; }

DB="drill_$(date +%s)"
cleanup() {
    docker compose -f "$HERE/compose.yml" exec -T postgres \
        psql -U "${POSTGRES_USER:-pseudex}" -d postgres \
        -c "DROP DATABASE IF EXISTS $DB" >/dev/null 2>&1 || true
    rm -f /tmp/license-drill.db
}
trap cleanup EXIT

# ── витрина ────────────────────────────────────────────────────────────────
DUMP="$(ls -t "$BACKUPS"/storefront-*.dump 2>/dev/null | head -1)"
[ -n "$DUMP" ] || fail "В $BACKUPS нет ни одного дампа витрины."

docker compose -f "$HERE/compose.yml" exec -T postgres \
    psql -U "${POSTGRES_USER:-pseudex}" -d postgres -c "CREATE DATABASE $DB" >/dev/null \
    || fail "Не удалось создать временную базу $DB."

if ! docker compose -f "$HERE/compose.yml" exec -T postgres \
        pg_restore -U "${POSTGRES_USER:-pseudex}" -d "$DB" --no-owner < "$DUMP" 2>/tmp/drill.err; then
    fail "pg_restore не смог развернуть $(basename "$DUMP"):
$(tail -5 /tmp/drill.err)"
fi

# Непустые таблицы, а не факт восстановления. Оборванный дамп разворачивается в
# пустую схему без единой ошибки.
ORGS="$(docker compose -f "$HERE/compose.yml" exec -T postgres \
        psql -U "${POSTGRES_USER:-pseudex}" -d "$DB" -tAc \
        "SELECT count(*) FROM billing_organization" 2>/dev/null || echo 0)"
[ "${ORGS:-0}" -gt 0 ] \
    || fail "Витрина развернулась, но в billing_organization ноль строк.
Файл $(basename "$DUMP") читается и при этом пуст — это худший вид бэкапа,
потому что он проходит проверку свежести."

# ── лицензии ───────────────────────────────────────────────────────────────
# Та самая база, которую нельзя пересобрать из кода.
LIC="$(ls -t "$BACKUPS"/license-*.db 2>/dev/null | head -1)"
[ -n "$LIC" ] || fail "В $BACKUPS нет ни одной копии базы лицензий."

cp "$LIC" /tmp/license-drill.db
KEYS="$(docker compose -f "$HERE/compose.yml" exec -T postgres \
        sh -c 'command -v sqlite3 >/dev/null && echo yes' 2>/dev/null || echo no)"
if [ "$KEYS" = "yes" ]; then
    COUNT="$(sqlite3 /tmp/license-drill.db "SELECT count(*) FROM keys" 2>/dev/null || echo -1)"
else
    # sqlite3 может не стоять на хосте; тогда проверяем хотя бы целостность
    # заголовка — это слабее, и об этом надо сказать, а не делать вид.
    COUNT="$(head -c 16 /tmp/license-drill.db | grep -c 'SQLite format 3' || echo 0)"
    [ "$COUNT" -gt 0 ] && COUNT=1
    notify warn "Учения: sqlite3 недоступен" \
        "Копия базы лицензий проверена только по заголовку, не по содержимому.
Поставьте sqlite3 на хост, чтобы учения проверяли то, ради чего существуют."
fi
[ "${COUNT:-0}" -gt 0 ] \
    || fail "Копия базы лицензий $(basename "$LIC") не читается или пуста.
Это единственное, что нельзя пересобрать из кода: без неё встанут ВСЕ
развёртывания в поле."

notify info "Учения по восстановлению пройдены" \
    "Витрина: $(basename "$DUMP"), организаций $ORGS.
Лицензии: $(basename "$LIC"), проверено.
Обе копии не просто свежие, а разворачиваются."
