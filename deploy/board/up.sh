#!/usr/bin/env bash
# Поднимает локальный стенд доски: наша сборка Vikunja за дверью Authelia.
#
# ИДЕМПОТЕНТЕН: секреты, пользователи и ключ создаются один раз и переиспользуются,
# поэтому повторный запуск ничего не ломает и не меняет (иначе уже выданные
# сессии и TOTP-устройства отваливались бы при каждом `./up.sh`).
#
# Пароль для всех пользователей стенда берётся из BOARD_PASSWORD (по умолчанию
# `pseudex`). Это ЛОКАЛЬНЫЙ стенд: слабый общий пароль здесь допустим ровно
# потому, что наружу он не смотрит. На проде у каждого свой пароль и TOTP.

set -euo pipefail
cd "$(dirname "$0")"

AUTHELIA_IMAGE="authelia/authelia:4.39"
BOARD_PASSWORD="${BOARD_PASSWORD:-pseudex}"
BOARD_USERS="${BOARD_USERS:-igor:Игорь gosha:Гоша ops:Оператор}"
FRONTEND_PATH="/ops-7f3a"

for tool in docker openssl python3; do
	command -v "$tool" >/dev/null || { echo "нужен $tool"; exit 1; }
done
docker compose version >/dev/null || { echo "нужен docker compose v2"; exit 1; }

# ── 1. Секреты стенда ────────────────────────────────────────────────────────
if [ ! -f .env ]; then
	cat > .env <<EOF
SESSION_SECRET=$(openssl rand -hex 32)
STORAGE_KEY=$(openssl rand -hex 32)
RESET_JWT_SECRET=$(openssl rand -hex 32)
OIDC_HMAC_SECRET=$(openssl rand -hex 32)
OIDC_CLIENT_SECRET=$(openssl rand -hex 24)
OIDC_STOREFRONT_SECRET=$(openssl rand -hex 24)
EOF
	chmod 600 .env
	echo "секреты созданы: board/.env"
fi
set -a; . ./.env; set +a

# ── 2. Пользователи команды ──────────────────────────────────────────────────
if [ ! -f authelia/users.yml ]; then
	echo "---" > authelia/users.yml
	echo "users:" >> authelia/users.yml
	for entry in $BOARD_USERS; do
		login="${entry%%:*}"
		display="${entry#*:}"
		hash=$(docker run --rm "$AUTHELIA_IMAGE" \
			authelia crypto hash generate argon2 --password "$BOARD_PASSWORD" --variant argon2id \
			| sed -n 's/^Digest: //p')
		[ -n "$hash" ] || { echo "не удалось посчитать хеш пароля"; exit 1; }
		{
			echo "  ${login}:"
			echo "    displayname: \"${display}\""
			echo "    password: \"${hash}\""
			echo "    email: \"${login}@pseudex.ru\""
		} >> authelia/users.yml
	done
	chmod 600 authelia/users.yml
	echo "пользователи созданы: authelia/users.yml (пароль всех: ${BOARD_PASSWORD})"
fi

# ── 3. Ключ подписи токенов OIDC ─────────────────────────────────────────────
if [ ! -f authelia/oidc.key ]; then
	openssl genrsa -out authelia/oidc.key 2048 2>/dev/null
	chmod 600 authelia/oidc.key
	echo "ключ OIDC создан: authelia/oidc.key"
fi

# ── 4. Рендер конфига с секретами ────────────────────────────────────────────
# Authelia сравнивает ДАЙДЖЕСТ секрета клиента, а Vikunja получает сам секрет —
# поэтому в конфиг едет хеш, в .env остаётся пароль.
digest=$(docker run --rm "$AUTHELIA_IMAGE" \
	authelia crypto hash generate pbkdf2 --password "$OIDC_CLIENT_SECRET" --variant sha512 \
	| sed -n 's/^Digest: //p')
[ -n "$digest" ] || { echo "не удалось посчитать дайджест секрета клиента доски"; exit 1; }
# Отдельный клиент для витрины: свой секрет, свой дайджест. Общий секрет на
# два приложения означал бы, что утечка одного открывает оба.
storefront_digest=$(docker run --rm "$AUTHELIA_IMAGE" \
	authelia crypto hash generate pbkdf2 --password "$OIDC_STOREFRONT_SECRET" --variant sha512 \
	| sed -n 's/^Digest: //p')
[ -n "$storefront_digest" ] || { echo "не удалось посчитать дайджест секрета витрины"; exit 1; }

python3 - "$digest" "$storefront_digest" <<'PY'
import pathlib, sys
digest = sys.argv[1]
storefront_digest = sys.argv[2]
tpl = pathlib.Path("authelia/configuration.yml").read_text()
key = pathlib.Path("authelia/oidc.key").read_text().strip()
key_block = "\n".join("          " + line for line in key.splitlines())
out = (tpl
       .replace("__SESSION_SECRET__", pathlib.Path(".env").read_text().split("SESSION_SECRET=")[1].splitlines()[0])
       .replace("__STORAGE_KEY__", pathlib.Path(".env").read_text().split("STORAGE_KEY=")[1].splitlines()[0])
       .replace("__RESET_JWT_SECRET__", pathlib.Path(".env").read_text().split("RESET_JWT_SECRET=")[1].splitlines()[0])
       .replace("__OIDC_HMAC_SECRET__", pathlib.Path(".env").read_text().split("OIDC_HMAC_SECRET=")[1].splitlines()[0])
       .replace("__OIDC_CLIENT_SECRET_DIGEST__", digest)
       .replace("__OIDC_STOREFRONT_SECRET_DIGEST__", storefront_digest)
       .replace("__OIDC_RSA_KEY__", key_block)
       # ДОМЕНЫ СТЕНДА. Тот же шаблон служит и проду: там эти пять строк
       # подставляет рендер в deploy/compose.yml, а здесь — стенд.
       .replace("__AUTH_URL__", "https://auth.lvh.me:8443")
       .replace("__COOKIE_DOMAIN__", "lvh.me")
       .replace("__BOARD_DOMAIN__", "board.lvh.me")
       .replace("__BOARD_URL__", "https://board.lvh.me:8443/ops-7f3a")
       .replace("__STOREFRONT_REDIRECT__", "https://pseudex.lvh.me:8443/backstage-7f3a/oidc/callback/"))
if "__" in out.replace("__", "__", 1):
    leftovers = [l for l in out.splitlines() if "__" in l]
    if leftovers:
        print("ОТКАЗ: в рендере остались плейсхолдеры:")
        print("\n".join(leftovers[:5]))
        sys.exit(1)
pathlib.Path("authelia/configuration.rendered.yml").write_text(out)
PY
chmod 600 authelia/configuration.rendered.yml
echo "конфиг отрендерен: authelia/configuration.rendered.yml"

# ── 5. Сборка и запуск ───────────────────────────────────────────────────────
if [ "${BOARD_RENDER_ONLY:-0}" = "1" ]; then
	echo "BOARD_RENDER_ONLY=1 — конфиг перерендерен, стенд не тронут"
	exit 0
fi

# ── 5. Порядок важен: сначала Caddy, потом остальные ─────────────────────────
#
# КОРНЕВОЙ СЕРТИФИКАТ НУЖЕН КОНТЕЙНЕРУ ДО СТАРТА. Vikunja ходит за OIDC на
# `https://auth.lvh.me:8443`, а это наш собственный CA; если файла нет в момент
# первого TLS-соединения, Go соберёт пул доверия без него и запомнит это.
# Поэтому CA выгружается из поднятого Caddy и монтируется файлом.
# Каталоги данных Vikunja: контейнер работает под uid 1000 и без прав не
# поднимется вовсе («failed to create test file» и рестарт по кругу).
mkdir -p data/db data/files
chmod 777 data/db data/files

# `--no-deps` ОБЯЗАТЕЛЕН. Без него compose поднимает и зависимости Caddy —
# включая Vikunja, — и она стартует на секунду РАНЬШЕ, чем появится корневой
# сертификат: Go собирает пул доверия один раз и запоминает его пустым.
docker compose up -d --no-deps caddy

for _ in $(seq 1 30); do
	if docker compose exec -T caddy test -f /data/caddy/pki/authorities/local/root.crt 2>/dev/null; then
		break
	fi
	sleep 1
done
# `docker compose` создаёт отсутствующий источник bind-mount КАТАЛОГОМ, поэтому
# перед записью убираем всё, что там оказалось.
rm -rf caddy-root.crt
docker compose exec -T caddy cat /data/caddy/pki/authorities/local/root.crt > caddy-root.crt
[ -s caddy-root.crt ] || { echo "не удалось получить корневой сертификат Caddy"; exit 1; }
echo "корневой сертификат Caddy: board/caddy-root.crt"

docker compose up -d --build

# ── 6. Сотрудник для демонстрации входа ──────────────────────────────────────
#
# Создаём staff-аккаунт и печатаем otpauth-URI: SSO пускает только существующих
# сотрудников (новых из токена не заводим), а аварийный вход требует TOTP —
# то есть обе двери должны быть открываемы, иначе демонстрация покажет одну.
docker compose exec -T storefront python - <<'PYEOF'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
django.setup()
from django.contrib.auth import get_user_model
U = get_user_model()
u, created = U.objects.get_or_create(
    email="igor@pseudex.ru",
    defaults={"is_staff": True, "is_superuser": True, "is_active": True},
)
if created:
    u.set_password(os.environ.get("BOARD_PASSWORD") or "pseudex")
    u.save()
print("сотрудник:", u.email, "(создан)" if created else "(уже был)")
PYEOF

cat <<EOF

────────────────────────────────────────────────────────────────
  Доска:      https://board.lvh.me:8443${FRONTEND_PATH}/
  Портал SSO: https://auth.lvh.me:8443
  Логины:     $(echo "$BOARD_USERS" | tr ' ' '\n' | cut -d: -f1 | paste -sd', ')
  Пароль:     ${BOARD_PASSWORD}   (меняется: BOARD_PASSWORD=... ./up.sh)

  Браузер один раз предупредит о сертификате: он выдан локальным CA Caddy,
  а не публичным. Принять — «Дополнительно» → «Перейти». При желании корневой
  сертификат лежит рядом (board/caddy-root.crt) и добавляется в связку ключей.

  Первый вход: пароль → и только потом доска. На проде здесь ещё и TOTP;

  Остановить:  docker compose down
  Посмотреть:  docker compose logs -f authelia
────────────────────────────────────────────────────────────────
EOF
