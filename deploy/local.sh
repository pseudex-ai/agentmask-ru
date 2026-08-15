#!/usr/bin/env bash
# Bring up the whole product locally and print the walkthrough.
#
# The signing key is generated once and cached, because it is compiled into the
# customer image: a fresh key would mean rebuilding that image every time this
# script runs, and the image takes minutes.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
KEYFILE="$HERE/.local-signing-key"

if [ ! -f "$KEYFILE" ]; then
    # Run from prototype/ so `licensing` is importable: __file__ is stdin here,
    # so the path trick that looked right resolved to the wrong directory.
    (cd "$ROOT/prototype" && ./.venv/bin/python -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from licensing.keys import encode_private
print(encode_private(Ed25519PrivateKey.generate()))
") > "$KEYFILE"
    echo "generated a local signing key -> $KEYFILE"
fi

PSEUDEX_SIGNING_KEY="$(head -1 "$KEYFILE")"
export PSEUDEX_SIGNING_KEY
PUBKEY="$(cd "$ROOT/prototype" && ./.venv/bin/python -c "
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from licensing.keys import encode_public
print(encode_public(Ed25519PrivateKey.from_private_bytes(base64.b64decode('$PSEUDEX_SIGNING_KEY')).public_key()))
")"

# The customer image, built against the SAME verification key the local
# licensing server signs with. Baked at build time exactly as in a release —
# a key the customer could override in the environment would let them sign
# their own bundles.
echo "building pseudex:source (verification key ${PUBKEY:0:12}…)"
docker build -q -f "$ROOT/prototype/Dockerfile" \
    --build-arg "PSEUDEX_LICENSE_PUBKEY=$PUBKEY" \
    -t pseudex:source "$ROOT/prototype" >/dev/null

docker compose -f "$HERE/compose.local.yml" up -d --build

# Django admin account. Cached like the signing key, so the link and password
# printed below stay valid across restarts — an admin whose password changed on
# every `up` is one nobody can keep a tab open on.
#
# Generated, never a literal: a password written into a script is a password
# that ships. This file is gitignored, and the account exists only on this
# machine's stand — it is not a credential for anything deployed.
ADMINFILE="$HERE/.local-admin"
if [ ! -f "$ADMINFILE" ]; then
    printf 'admin@pseudex.local\n%s\n' "$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20)" > "$ADMINFILE"
    chmod 600 "$ADMINFILE"
fi
ADMIN_EMAIL="$(sed -n 1p "$ADMINFILE")"
ADMIN_PASSWORD="$(sed -n 2p "$ADMINFILE")"

# Wait for the schema: the container runs `migrate` at start, and creating a
# user against a half-migrated database fails in a way that looks like a bug.
for _ in $(seq 1 30); do
    curl -fsS -o /dev/null "http://localhost:8080/healthz" 2>/dev/null && break
    sleep 1
done

docker compose -f "$HERE/compose.local.yml" exec -T \
    -e ADMIN_EMAIL="$ADMIN_EMAIL" -e ADMIN_PASSWORD="$ADMIN_PASSWORD" \
    storefront python manage.py shell -c '
import os
from django.contrib.auth import get_user_model
User = get_user_model()
email, password = os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"]
user, created = User.objects.get_or_create(email=email)
# Reset every run: the cached file is the source of truth, so a password
# changed by hand in the admin stops matching what this script prints.
user.is_staff = user.is_superuser = user.is_active = True
user.set_password(password)
user.save()
print("админ создан" if created else "админ обновлён")
' >/dev/null 2>&1 && echo "  админ: $ADMIN_EMAIL" || echo "  админа создать не удалось — см. логи витрины"

cat <<TEXT

────────────────────────────────────────────────────────────────────
  Стенд поднят. Пройдите путь клиента:

  1. Откройте лендинг            http://localhost:8080
  2. Внизу «Быстрый старт» — введите любой email, получите ключ.
     Ключ показывается ОДИН раз, скопируйте команду целиком.

  3. Запустите контейнер (ключ уже подставлен на странице), но
     добавьте адрес локального лицензионного сервера:

     docker run -d --name pseudex -p 8000:8000 -p 127.0.0.1:8081:8081 \\
       -v pseudex-data:/data \\
       -e PSEUDEX_LICENSE_KEY=<ваш ключ> \\
       -e PSEUDEX_LICENSE_URL=http://host.docker.internal:8443 \\
       pseudex:source

  4. Ссылка на локальный интерфейс — в логе контейнера:
     docker logs pseudex 2>&1 | grep "локальный интерфейс" -A2

  5. Письма для входа в кабинет печатаются в лог витрины:
     docker compose -f deploy/compose.local.yml logs storefront | grep -A4 "http"

  6. Django-админка          http://localhost:8080/admin/
     логин / пароль — в deploy/.local-admin (gitignored, только этот стенд)

  Аренда здесь живёт 5 минут, grace 10 — лестницу деградации
  можно пройти целиком, не дожидаясь суток.

  Погасить:  docker compose -f deploy/compose.local.yml down -v
             docker rm -f pseudex
────────────────────────────────────────────────────────────────────
TEXT
