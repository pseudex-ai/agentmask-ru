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
    rm -f /tmp/license-drill.db /tmp/drill-lic.err
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

# ПРОВЕРЯЕТ ОБРАЗ ЛИЦЕНЗИЙ, А НЕ ХОСТ. Раньше здесь звался хостовый sqlite3, а
# когда его не было — проверялся заголовок файла. Обе половины плохи, и вторая
# стала хуже:
#
#   * заголовок — ровно та слабая проверка, которую отвергает docs/decisions.md:
#     оборванный дамп читается прекрасно, разворачивается в пустоту и проходит
#     проверку свежести. Учения существуют именно против этого;
#   * хостовый sqlite3 не умеет SQLCipher, поэтому на зашифрованной копии он
#     отвечает «file is not a database» — то есть кричал бы каждое воскресенье
#     на исправном бэкапе. Замьюченный канал и есть цена такой тревоги.
#
# `licensing.verify` внутри образа открывает копию ТОЙ ЖЕ фабрикой соединений,
# что и продукт, и считает СТРОКИ. Открыть не смог — учения провалены, без
# «зато заголовок на месте».
LIC_CONTAINER="$(docker compose -f "$HERE/compose.yml" ps -q license 2>/dev/null || true)"
[ -n "$LIC_CONTAINER" ] || fail "Контейнер лицензий не запущен — учения нечем
проводить: проверка открывает копию тем же кодом, что и продукт."
LIC_IMAGE="$(docker inspect --format '{{.Config.Image}}' "$LIC_CONTAINER")"

# Одноразовый контейнер из того же образа: боевой не трогается вовсе.
if ! ROWS="$(docker run --rm -v /tmp/license-drill.db:/verify/license.db:ro \
        "$LIC_IMAGE" python -m licensing.verify /verify/license.db 2>/tmp/drill-lic.err)"; then
    fail "Копия базы лицензий $(basename "$LIC") не открывается или пуста:
$(tail -3 /tmp/drill-lic.err)
Это единственное, что нельзя пересобрать из кода: без неё встанут ВСЕ
развёртывания в поле."
fi
COUNT="$(printf '%s\n' "$ROWS" | sed -n 's/^keys=//p')"

notify info "Учения по восстановлению пройдены" \
    "Витрина: $(basename "$DUMP"), организаций $ORGS.
Лицензии: $(basename "$LIC"), ключей ${COUNT:-?}.
Обе копии не просто свежие, а разворачиваются."
