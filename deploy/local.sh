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
    "$ROOT/prototype/.venv/bin/python" - > "$KEYFILE" <<'PY'
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from licensing.keys import encode_private, encode_public
key = Ed25519PrivateKey.generate()
print(encode_private(key))
print(encode_public(key.public_key()), file=sys.stderr)
PY
    echo "generated a local signing key -> $KEYFILE"
fi

VEILGATE_SIGNING_KEY="$(head -1 "$KEYFILE")"
export VEILGATE_SIGNING_KEY
PUBKEY="$("$ROOT/prototype/.venv/bin/python" -c "
import base64, sys
sys.path.insert(0, '$ROOT/prototype')
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from licensing.keys import encode_public
print(encode_public(Ed25519PrivateKey.from_private_bytes(base64.b64decode('$VEILGATE_SIGNING_KEY')).public_key()))
")"

# The customer image, built against the SAME verification key the local
# licensing server signs with. Baked at build time exactly as in a release —
# a key the customer could override in the environment would let them sign
# their own bundles.
echo "building veilgate:source (verification key ${PUBKEY:0:12}…)"
docker build -q -f "$ROOT/prototype/Dockerfile" \
    --build-arg "VEILGATE_LICENSE_PUBKEY=$PUBKEY" \
    -t veilgate:source "$ROOT/prototype" >/dev/null

docker compose -f "$HERE/compose.local.yml" up -d --build

cat <<TEXT

────────────────────────────────────────────────────────────────────
  Стенд поднят. Пройдите путь клиента:

  1. Откройте лендинг            http://localhost:8080
  2. Внизу «Быстрый старт» — введите любой email, получите ключ.
     Ключ показывается ОДИН раз, скопируйте команду целиком.

  3. Запустите контейнер (ключ уже подставлен на странице), но
     добавьте адрес локального лицензионного сервера:

     docker run -d --name veilgate -p 8000:8000 -p 127.0.0.1:8081:8081 \\
       -v veilgate-data:/data \\
       -e VEILGATE_LICENSE_KEY=<ваш ключ> \\
       -e VEILGATE_LICENSE_URL=http://host.docker.internal:8443 \\
       veilgate:source

  4. Ссылка на локальный интерфейс — в логе контейнера:
     docker logs veilgate 2>&1 | grep "локальный интерфейс" -A2

  5. Письма для входа в кабинет печатаются в лог витрины:
     docker compose -f deploy/compose.local.yml logs storefront | grep -A4 "http"

  Аренда здесь живёт 5 минут, grace 10 — лестницу деградации
  можно пройти целиком, не дожидаясь суток.

  Погасить:  docker compose -f deploy/compose.local.yml down -v
             docker rm -f veilgate
────────────────────────────────────────────────────────────────────
TEXT
