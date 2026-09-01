#!/bin/sh
# Сторож: превращает список из docs/operations.md §5 в механизм.
#
# ПОЧЕМУ ОН ВООБЩЕ ЕСТЬ. §5 перечислял, за чем смотреть — место на диске,
# свежесть бэкапа, жив ли лицензионный сервер. Это была инструкция человеку, а
# человек не смотрит. Всё, что здесь проверяется, проверялось и раньше — просто
# глазами и по случаю.
#
# ТРЕВОГА НА СМЕНУ СОСТОЯНИЯ, А НЕ НА КАЖДЫЙ ОБХОД. Это главное свойство файла.
# Сторож, который раз в минуту повторяет «диск заполнен», за час обучает
# замьютить канал — и следующая, настоящая тревога придёт в замьюченный канал.
# Поэтому каждая проверка помнит свой прошлый вердикт и говорит дважды: когда
# сломалось и когда починилось. Второе не менее важно: тревога без отбоя
# оставляет человека гадать, чинилось ли оно вообще.
#
# ЧТО СЮДА НЕ ПОПАДАЕТ. Логи и содержимое ответов — в них персональные данные
# клиентов. Сторож сообщает ФАКТ и место, дальше человек идёт смотреть сам. То
# же правило, по которому журнал раскрытий не хранит значение.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
STATE_DIR="${PSEUDEX_WATCH_STATE:-$HERE/.watch}"
COMPOSE="$HERE/compose.yml"
BACKUPS="${PSEUDEX_BACKUP_DIR:-$HERE/backups}"
LICENSE_ADMIN="${PSEUDEX_LICENSE_ADMIN:-http://license:9443}"
mkdir -p "$STATE_DIR"

notify() { "$HERE/notify.sh" "$@" || true; }

# report NAME OK|FAIL LEVEL "заголовок" "тело"
# Пишет только на переходе. Возвращает 0 всегда — обход не должен прерываться
# из-за одной сломанной проверки.
report() {
    name="$1"; verdict="$2"; level="$3"; title="$4"; body="$5"
    file="$STATE_DIR/$name"
    prev="$(cat "$file" 2>/dev/null || echo OK)"
    printf '%s' "$verdict" > "$file"
    [ "$verdict" = "$prev" ] && return 0
    if [ "$verdict" = "FAIL" ]; then
        notify "$level" "$title" "$body"
    else
        notify info "Отбой: $title" "Проверка снова проходит."
    fi
}

# ── 1. место на диске ───────────────────────────────────────────────────────
# Единственный отказ из §2, который останавливает ВСЕХ клиентов сразу: без
# места лицензионный сервер не пишет аренду, а без аренды через двое суток
# grace встают все развёртывания в поле.
USED="$(df -P / | awk 'NR==2 {gsub("%","",$5); print $5}')"
if [ "${USED:-0}" -ge 85 ]; then
    report disk FAIL crit "Диск заполнен на ${USED}%" \
        "Без места лицензионный сервер перестанет выдавать аренду, и через двое
суток grace встанут ВСЕ клиенты. Смотрите docker system df и $BACKUPS."
else
    report disk OK info "Диск заполнен на ${USED}%" ""
fi

# ── 2. свежесть бэкапа ──────────────────────────────────────────────────────
# «Бэкап, который никто не проверял, — это отсутствующий бэкап» (§5). Проверка
# по МЛАДШЕМУ файлу каждого вида: одна свежая копия витрины не заменяет
# протухшую копию лицензий, а именно лицензии невосстановимы из кода.
for kind in storefront license; do
    newest="$(find "$BACKUPS" -name "${kind}-*" -type f -mmin -1500 2>/dev/null | head -1)"
    if [ -z "$newest" ]; then
        report "backup-$kind" FAIL crit "Бэкап $kind старше 25 часов" \
            "В $BACKUPS нет свежего файла ${kind}-*.
База лицензий — единственное, что нельзя пересобрать из кода: потеря
останавливает все развёртывания в поле, и никакой код этого не вернёт."
    else
        report "backup-$kind" OK info "Бэкап $kind свежий" ""
    fi
done

# ── 3. контейнеры ───────────────────────────────────────────────────────────
# Здоровье, а не факт запуска: `running` бывает и у процесса, который упал в
# цикл рестарта секунду назад.
BAD="$(docker compose -f "$COMPOSE" ps --format '{{.Service}} {{.Health}} {{.State}}' 2>/dev/null \
       | awk '$2 == "unhealthy" || ($2 == "" && $3 != "running") { print $1 }' | tr '\n' ' ')"
if [ -n "$BAD" ]; then
    report containers FAIL crit "Сервисы нездоровы: $BAD" \
        "docker compose -f $COMPOSE ps
Логи не пересылаю — в них могут быть данные клиентов."
else
    report containers OK info "Все сервисы здоровы" ""
fi

# ── 4. лицензионный сервер отвечает ─────────────────────────────────────────
# Изнутри сети стенда, а не снаружи: снаружи за него смотрит внешняя проверка
# (.github/workflows/uptime.yml), и разделение намеренное — эта видит «процесс
# жив», та видит «машина жива». Совпадать они не обязаны.
if curl -sS --max-time 10 -o /dev/null -w '%{http_code}' \
        -H "Authorization: Bearer ${PSEUDEX_LICENSE_ADMIN_TOKEN:-}" \
        "$LICENSE_ADMIN/admin/list" 2>/dev/null | grep -q '^200$'; then
    report license-admin OK info "Лицензионный сервер отвечает" ""
else
    report license-admin FAIL crit "Лицензионный сервер не отвечает" \
        "$LICENSE_ADMIN/admin/list не вернул 200.
Клиенты держатся на grace: сутки аренды плюс двое суток льготы. Времени есть,
но оно идёт."
fi

# ── 5. клиенты, которые вот-вот встанут ─────────────────────────────────────
# Единственный пункт §5, который стоит превращать в письмо клиенту ДО того, как
# он позвонит. Уровень warn, а не crit: у нас ничего не сломано, ломается у
# него, и разбудить это должно рабочее утро, а не ночь.
#
# ПРОВЕРКА БЫЛА ВСЕГДА ПУСТОЙ. Она читает `last_lease`, а `/admin/list` такого
# поля не отдавал — то есть сигнал «клиент перестал продлеваться» не приходил
# никогда. А это ровно тот сигнал, который поймал бы и блэкхол лицензионного
# сервера, и повтор захваченной лизы: и то и другое выглядит отсюда одинаково.
# Поле теперь отдаётся, и проверка наконец делает то, что описано в §5.
STALE="$(curl -sS --max-time 10 -H "Authorization: Bearer ${PSEUDEX_LICENSE_ADMIN_TOKEN:-}" \
         "$LICENSE_ADMIN/admin/list" 2>/dev/null \
         | python3 -c '
import json, sys, time
try:
    rows = json.load(sys.stdin)
except Exception:
    sys.exit(0)
rows = rows.get("orgs", rows) if isinstance(rows, dict) else rows
now = time.time()
late = [r.get("org_id") for r in rows if isinstance(r, dict)
        and r.get("last_lease") and now - float(r["last_lease"]) > 86400]
print(" ".join(str(o) for o in late[:20]))' 2>/dev/null || echo "")"
if [ -n "$STALE" ]; then
    report stale-instances FAIL warn "Не продлевают аренду больше суток: $STALE" \
        "Клиент вот-вот встанет и, скорее всего, ещё не знает об этом.
Это тот случай, когда письмо стоит написать до звонка."
else
    report stale-instances OK info "Все аренды продлеваются" ""
fi

# ── 6. срок сертификата ─────────────────────────────────────────────────────
# Caddy продлевает сам и делает это надёжно — но молчаливый отказ продления
# кладёт сайт целиком, и узнать о нём за две недели стоит одной проверки.
if [ -n "${SITE_HOST:-}" ]; then
    LEFT="$(echo | openssl s_client -servername "$SITE_HOST" -connect "$SITE_HOST:443" 2>/dev/null \
            | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
    if [ -n "$LEFT" ]; then
        DAYS=$(( ( $(date -d "$LEFT" +%s 2>/dev/null || echo 0) - $(date +%s) ) / 86400 ))
        if [ "$DAYS" -lt 14 ] && [ "$DAYS" -gt -3650 ]; then
            report cert FAIL warn "Сертификат $SITE_HOST истекает через $DAYS дн." \
                "Caddy продлевает сам; если счётчик не растёт — продление молча не работает."
        else
            report cert OK info "Сертификат $SITE_HOST в порядке" ""
        fi
    fi
fi
