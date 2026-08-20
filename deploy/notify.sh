#!/bin/sh
# Один канал тревоги на всё: выкатку, сторожа и бэкап.
#
# ПОЧЕМУ ОТДЕЛЬНЫЙ ФАЙЛ, А НЕ ТРИ CURL'А. Отправка — единственное место, где
# ошибка молчалива по своей природе: если она сломается, всё остальное
# продолжит работать и никто об этом не узнает. Поэтому она одна, и её отказ
# печатается в лог контейнера, где его увидит `docker logs`.
#
# ТЕЛЕГРАМ, А НЕ ПОЧТА, — по решению от 20.08.2026 (docs/decisions.md):
# письмо о падении в три ночи читается утром, сообщение в канал — сразу.
#
# usage:  notify.sh LEVEL "заголовок" "тело"
#         LEVEL = info | warn | crit
set -eu

LEVEL="${1:-info}"
TITLE="${2:-}"
BODY="${3:-}"

if [ -z "${PSEUDEX_TG_TOKEN:-}" ] || [ -z "${PSEUDEX_TG_CHAT:-}" ]; then
    # НЕ молча. Ненастроенная тревога — это отсутствующая тревога, и узнать об
    # этом надо в тот момент, когда она впервые понадобилась, а не после.
    echo "notify: PSEUDEX_TG_TOKEN/PSEUDEX_TG_CHAT не заданы — [$LEVEL] $TITLE: $BODY" >&2
    exit 0
fi

case "$LEVEL" in
    crit) MARK="🔴" ;;
    warn) MARK="🟡" ;;
    *)    MARK="⚪️" ;;
esac

HOST="${PSEUDEX_ENV_NAME:-$(hostname)}"

# HTML, а не Markdown: тело почти всегда содержит вывод команды со скобками,
# подчёркиваниями и звёздочками, и Markdown на нём разваливается — сообщение
# либо не отправляется, либо приходит покорёженным ровно в тот момент, когда
# его читают внимательнее всего.
escape() { printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g'; }

TEXT="$MARK <b>$(escape "$TITLE")</b>
<i>$(escape "$HOST")</i>

<pre>$(escape "$BODY")</pre>"

# Тревога не должна валить того, кто её послал: сторож обязан продолжить обход,
# даже если Телеграм недоступен. Отказ печатается и проглатывается.
if ! curl -sS --max-time 15 -o /dev/null \
        "https://api.telegram.org/bot${PSEUDEX_TG_TOKEN}/sendMessage" \
        -d "chat_id=${PSEUDEX_TG_CHAT}" \
        -d "parse_mode=HTML" \
        --data-urlencode "text=${TEXT}"; then
    echo "notify: не удалось отправить [$LEVEL] $TITLE" >&2
fi
