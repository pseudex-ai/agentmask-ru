#!/bin/sh
# Еженедельная уборка диска. Идёт таймером НЕЗАВИСИМО от выкаток.
#
# ЗАЧЕМ, ЕСЛИ АГЕНТ УЖЕ ЧИСТИТ ОБРАЗЫ. Агент чистит ПОСЛЕ выкатки, а между
# выкатками копится другое: кеш сборки, остановленные контейнеры отладки,
# висячие слои от `docker pull` руками, сети от compose-стендов. Без места
# лицензионный сервер перестаёт выдавать аренду, и через двое суток grace
# встают ВСЕ клиенты — сторож кричит на 85%, но кричать и убирать — разное.
#
# ТОМА НЕ ТРОГАЮТСЯ, И ЭТО НЕ ОСТОРОЖНОСТЬ, А ГРАНИЦА. `--volumes` удаляет
# «неиспользуемые» именованные тома — а том Grafana «не используется» ровно в
# ту минуту, когда профиль observability остановлен для отладки. Данные
# удаляют руками и глядя; всё остальное — этот файл.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
notify() { "$HERE/notify.sh" "$@" || true; }

BEFORE="$(df -P / | awk 'NR==2 {print $5}')"

docker container prune -f --filter "until=24h" >/dev/null 2>&1 || true
docker image prune -af --filter "until=168h" >/dev/null 2>&1 || true
docker builder prune -af --filter "until=168h" >/dev/null 2>&1 || true
docker network prune -f >/dev/null 2>&1 || true

# journald без потолка растёт до 10% диска по умолчанию; 500 МБ хватает на
# месяцы системных логов, а логи сервисов живут в json-файлах и в Loki.
journalctl --vacuum-size=500M >/dev/null 2>&1 || true
apt-get clean >/dev/null 2>&1 || true

AFTER="$(df -P / | awk 'NR==2 {print $5}')"
echo "housekeeping: диск ${BEFORE} -> ${AFTER}"
# Сообщение только если освободили заметно: уборка, которая пишет каждую
# неделю «ничего не изменилось», учит не читать канал.
B="${BEFORE%\%}"; A="${AFTER%\%}"
[ "$((B - A))" -ge 5 ] && notify info "Уборка диска: ${BEFORE} → ${AFTER}" "docker prune + journald vacuum"
exit 0
