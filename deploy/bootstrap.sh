#!/usr/bin/env bash
# Превратить ЧИСТУЮ Ubuntu 24.04 в боевой хост pseudex. Одна команда, идемпотентно.
#
#   sudo bash deploy/bootstrap.sh
#
# ПОЧЕМУ СКРИПТ, А НЕ ИНСТРУКЦИЯ. Инструкция выполняется по-разному каждый раз, и
# разница всплывает через полгода как «на той машине работало». Здесь же машину
# можно пересоздать с нуля за десять минут, а это и есть настоящая защита от
# отказа хоста — резервная копия без умения быстро развернуть её бесполезна.
#
# ЧЕГО ЭТОТ СКРИПТ НАМЕРЕННО НЕ ДЕЛАЕТ:
#   * не поднимает стек — для этого есть агент, и он проверяет подписи;
#   * не создаёт секретов — их приносит человек, и `.env` остаётся его работой;
#   * не трогает DNS — запись A ставится ПОСЛЕ того, как стек отвечает по IP,
#     иначе Let's Encrypt копит неудачные попытки на домен.
set -euo pipefail

REPO_URL="${PSEUDEX_REPO_URL:-git@github.com:Isk4R1oT/Obscura.git}"
TARGET="${PSEUDEX_ROOT:-/opt/pseudex}"
SSH_PORT="${PSEUDEX_SSH_PORT:-22}"

# ДВЕ РОЛИ, ОДНА ЗАКАЛКА. Машина аналитики — такая же машина в том же интернете:
# ей нужны те же обновления безопасности, тот же закрытый фаервол, тот же
# выключенный парольный ssh и тот же лимит на логи. Разница только в том, ЧТО на
# ней крутится, и начинается она с шага 8. Второй скрипт с копией первых семи
# шагов разошёлся бы с оригиналом на первой же правке — а расходятся такие
# копии всегда в сторону «на той машине забыли закрыть порт».
#
#   app        витрина, лицензионный сервер, наблюдаемость   (по умолчанию)
#   analytics  PostHog: своя аналитика, свой домен, свои 8 ГБ
ROLE="${PSEUDEX_BOOTSTRAP_ROLE:-app}"
case "$ROLE" in app|analytics) : ;; *) echo "PSEUDEX_BOOTSTRAP_ROLE: app или analytics"; exit 1 ;; esac

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
warn() { printf '\033[33m!! %s\033[0m\n' "$*" >&2; }

[ "$(id -u)" -eq 0 ] || { echo "нужен root: sudo bash $0"; exit 1; }
. /etc/os-release
case "${ID}:${VERSION_ID}" in
    ubuntu:24.04|ubuntu:22.04|debian:12) : ;;
    *) warn "проверено на Ubuntu 22.04/24.04 и Debian 12, здесь ${PRETTY_NAME} — продолжаю, но читайте вывод внимательно" ;;
esac

say "1/9 обновления и базовые пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
    ca-certificates curl git gnupg ufw fail2ban unattended-upgrades \
    apt-listchanges chrony jq sqlite3 >/dev/null

say "2/9 автоматические обновления безопасности"
# БЕЗ ЭТОГО МАШИНА СТАРЕЕТ МОЛЧА. Ядро и openssl чинятся не тогда, когда мы
# вспомним, а тогда, когда вышла заплатка; перезагрузка НЕ автоматическая
# намеренно — её выбирает человек, потому что она роняет обслуживание.
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
cat > /etc/apt/apt.conf.d/51pseudex-unattended <<'EOF'
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
EOF

say "3/9 фаервол"
# ПО УМОЛЧАНИЮ ЗАКРЫТО. Наружу смотрят ровно три порта: ssh, http (только ради
# редиректа и ACME) и https. Ни Postgres, ни Prometheus, ни админский порт
# лицензионного сервера наружу не публикуются — и не должны появиться здесь
# «на время отладки».
ufw --force reset >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw allow "${SSH_PORT}/tcp" comment 'ssh' >/dev/null
ufw allow 80/tcp comment 'http -> редирект и ACME' >/dev/null
ufw allow 443/tcp comment 'https' >/dev/null
ufw --force enable >/dev/null
ufw status numbered | sed 's/^/    /'

say "4/9 ssh"
# ПАРОЛЬНЫЙ ВХОД ВЫКЛЮЧАЕТСЯ ТОЛЬКО ЕСЛИ КЛЮЧ УЖЕ ЛЕЖИТ. Иначе скрипт запер бы
# оператора снаружи собственной машины — самый дорогой способ повысить
# безопасность.
KEYS_FOUND=0
for f in /root/.ssh/authorized_keys /home/*/.ssh/authorized_keys; do
    [ -s "$f" ] && KEYS_FOUND=$((KEYS_FOUND + 1))
done
if [ "$KEYS_FOUND" -gt 0 ]; then
    cat > /etc/ssh/sshd_config.d/99-pseudex.conf <<EOF
Port ${SSH_PORT}
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
X11Forwarding no
MaxAuthTries 3
EOF
    sshd -t && systemctl reload ssh 2>/dev/null || systemctl reload sshd
    echo "    парольный вход выключен (найдено файлов с ключами: ${KEYS_FOUND})"
else
    warn "ключей SSH не найдено — парольный вход ОСТАВЛЕН включённым."
    warn "положите ключ и перезапустите скрипт, иначе машина открыта для перебора."
fi
systemctl enable --now fail2ban >/dev/null 2>&1 || true

say "5/9 swap"
# ПОЧЕМУ ВООБЩЕ. Стек модели держит ~350 МБ на воркер, а сборка и миграции дают
# короткие пики. Без swap OOM-killer выбирает жертву сам, и его вердикт — код
# 137, не называющий ни памяти, ни нас.
if ! swapon --show | grep -q .; then
    RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
    SWAP_GB=$(( RAM_MB < 4096 ? 4 : 2 ))
    fallocate -l "${SWAP_GB}G" /swapfile
    chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    # Своп нужен как подушка, а не как второй уровень памяти: 10 означает
    # «трогай только под давлением».
    sysctl -qw vm.swappiness=10
    grep -q '^vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
    echo "    добавлено ${SWAP_GB} ГБ swap"
else
    echo "    swap уже есть"
fi

say "6/9 docker"
if ! command -v docker >/dev/null 2>&1; then
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin >/dev/null
fi
# ЛОГИ КОНТЕЙНЕРОВ ОГРАНИЧИВАЮТСЯ НА УРОВНЕ ДЕМОНА ТОЖЕ. В compose лимит стоит,
# но контейнер, поднятый руками в отладке, съест диск — а без места
# лицензионный сервер перестаёт выдавать аренду, и через двое суток grace
# встают ВСЕ клиенты.
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "5" },
  "live-restore": true
}
EOF
systemctl enable --now docker >/dev/null
systemctl restart docker
docker --version | sed 's/^/    /'

say "7/9 cosign"
# АГЕНТ БЕЗ COSIGN НЕ ВЫКАТИТ НИЧЕГО, и это правильно: проверка подписи стоит
# ДО остановки сервисов, поэтому отсутствие инструмента — отказ выкатки, а не
# выкатка без проверки.
if ! command -v cosign >/dev/null 2>&1; then
    COSIGN_VER="v2.4.1"
    ARCH="$(dpkg --print-architecture)"
    curl -fsSL -o /usr/local/bin/cosign \
        "https://github.com/sigstore/cosign/releases/download/${COSIGN_VER}/cosign-linux-${ARCH}"
    chmod +x /usr/local/bin/cosign
fi
cosign version 2>&1 | grep -i version | head -1 | sed 's/^/    /'

if [ "$ROLE" = "analytics" ]; then
    say "8/8 машина аналитики готова"
    RAM_GB=$(( $(free -m | awk '/^Mem:/{print $2}') / 1024 ))
    if [ "$RAM_GB" -lt 7 ]; then
        warn "памяти ${RAM_GB} ГБ. PostHog поднимает ClickHouse, Kafka, Redis,"
        warn "Postgres и MinIO: меньше 8 ГБ он стартует и падает под нагрузкой,"
        warn "а падает он молча — графики просто перестают обновляться."
    fi
    cat <<'EOF'

    Дальше — установщик PostHog, он сам поднимет свой стек и получит сертификат:

      DOMAIN=analytics.pseudex.ru /bin/bash -c "$(curl -fsSL https://get.posthog.com)"

    ПОСЛЕ УСТАНОВКИ ОБЯЗАТЕЛЬНО, И ЭТО НЕ ФОРМАЛЬНОСТЬ:

      1. Отключить телеметрию наружу. Organization settings -> Anonymize data.
         Продукт продаёт «данные не покидают контур»; собственная аналитика,
         звонящая домой, — это не мелочь.
      2. Data retention — 90 дней. По умолчанию PostHog хранит вечно, а хранить
         вечно то, что описывает поведение людей, значит держать у себя данные,
         за которые придётся отвечать без единой причины их иметь.
      3. Session replay: masking включён на стороне сайта (`analytics.js`), но
         проверьте, что в записи действительно не видно набранной почты. Это
         проверяется глазами один раз и стоит того.
      4. Ключ проекта (`phc_...`) — в deploy/.env боевой машины как
         PSEUDEX_ANALYTICS_KEY, адрес — как PSEUDEX_ANALYTICS_HOST.
      5. Бэкап PostHog НЕ настраивается. Это намеренно: поведенческие данные
         восстанавливать неоткуда и незачем, а машина пересоздаётся этим же
         скриптом за десять минут. То, что обязано пережить пожар, — базы
         витрины и лицензий, и они вывозятся restic-ом с другой машины.

EOF
    exit 0
fi

say "8/9 репозиторий и systemd"
if [ ! -d "${TARGET}/.git" ]; then
    mkdir -p "$(dirname "${TARGET}")"
    git clone --quiet "${REPO_URL}" "${TARGET}" || {
        warn "не смог склонировать ${REPO_URL}"
        warn "положите ключ развёртывания и повторите, либо задайте PSEUDEX_REPO_URL"
        exit 1
    }
fi
install -m 0644 "${TARGET}/deploy/systemd/pseudex-agent.service" /etc/systemd/system/
install -m 0644 "${TARGET}/deploy/systemd/pseudex-agent.timer" /etc/systemd/system/
install -m 0644 "${TARGET}/deploy/systemd/pseudex-restore-drill.service" /etc/systemd/system/
install -m 0644 "${TARGET}/deploy/systemd/pseudex-restore-drill.timer" /etc/systemd/system/
install -m 0644 "${TARGET}/deploy/systemd/pseudex-housekeeping.service" /etc/systemd/system/
install -m 0644 "${TARGET}/deploy/systemd/pseudex-housekeeping.timer" /etc/systemd/system/
# journald: потолок сразу, а не когда диск кончится.
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=500M\n' > /etc/systemd/journald.conf.d/pseudex.conf
systemctl restart systemd-journald
systemctl daemon-reload
systemctl enable --now pseudex-agent.timer pseudex-restore-drill.timer pseudex-housekeeping.timer >/dev/null
systemctl list-timers --no-pager pseudex-\* | sed 's/^/    /' | head -5

say "9/9 что осталось человеку"
ENVFILE="${TARGET}/deploy/.env"
if [ ! -f "${ENVFILE}" ]; then
    umask 077
    cat > "${ENVFILE}" <<'EOF'
# Секреты боевого хоста. НЕ В ГИТЕ. Права 600.
SITE_HOST=pseudex.ru
LICENSE_HOST=license.pseudex.ru
REGISTRY=cr.yandex/ЗАПОЛНИТЕ
PSEUDEX_ENV_NAME=prod

POSTGRES_PASSWORD=ЗАПОЛНИТЕ
PSEUDEX_SECRET_KEY=ЗАПОЛНИТЕ
PSEUDEX_SIGNING_KEY=ЗАПОЛНИТЕ
PSEUDEX_TUNING_KEY=ЗАПОЛНИТЕ
PSEUDEX_LICENSE_ADMIN_TOKEN=ЗАПОЛНИТЕ

PSEUDEX_TG_TOKEN=ЗАПОЛНИТЕ
PSEUDEX_TG_CHAT=ЗАПОЛНИТЕ

# Бот поддержки — ОТДЕЛЬНЫЙ. Группа операторов — супергруппа, id вида -100…
PSEUDEX_SUPPORT_BOT_TOKEN=ЗАПОЛНИТЕ
PSEUDEX_SUPPORT_CHAT=ЗАПОЛНИТЕ
PSEUDEX_SUPPORT_OWNER=ЗАПОЛНИТЕ
PSEUDEX_SUPPORT_BOT=pseudex_support_bot

# Вывоз копий. Пусто — копии остаются ТОЛЬКО на этой машине.
RESTIC_REPOSITORY=s3:https://storage.yandexcloud.net/ЗАПОЛНИТЕ
RESTIC_PASSWORD=ЗАПОЛНИТЕ
OFFSITE_KEY_ID=ЗАПОЛНИТЕ
OFFSITE_KEY_SECRET=ЗАПОЛНИТЕ
EOF
    echo "    создан ${ENVFILE} — заполните и запустите снова"
fi

LEFT="$(grep -c 'ЗАПОЛНИТЕ' "${ENVFILE}" || true)"
echo
if [ "${LEFT}" -gt 0 ]; then
    warn "в ${ENVFILE} осталось незаполненных значений: ${LEFT}"
    warn "стек НЕ поднимется, пока они там — и это правильно: пустой секрет"
    warn "поднимает сервис, который выглядит работающим и им не является."
else
    echo "    .env заполнен"
fi
cat <<EOF

Машина готова. Дальше:

  1. docker login ${REGISTRY:-cr.yandex/...} — ключом сервисного аккаунта
     pseudex-host с ролью container-registry.images.puller (ТОЛЬКО качать).
  2. git tag -a v0.1.0 -m "первый релиз" && git push --tags   (или из GitHub)
  3. Агент сам увидит тег, проверит подписи и поднимет стек — раз в минуту.
  4. Убедиться, что стек отвечает по IP, и ТОЛЬКО ПОТОМ добавлять запись A.

  systemctl list-timers 'pseudex-*'   что и когда бежит
  journalctl -u pseudex-agent -f      как идёт выкатка
  docker compose -f ${TARGET}/deploy/compose.yml ps

EOF
