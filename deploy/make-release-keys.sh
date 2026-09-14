#!/usr/bin/env bash
# Ключ подписи Ed25519 — КОМПИЛИРУЕТСЯ В РЕЛИЗНЫЙ БИНАРНИК (публичная половина),
# создаётся ОДИН РАЗ на всю жизнь продукта. Тюнинг едет в лизе, отдельного
# ключа тюнинга больше нет (docs/tz-tuning-in-lease.md).
#
# ПОЧЕМУ ОДИН РАЗ, А НЕ НА КАЖДУЮ СБОРКУ. Публичная половина ключа подписи
# вкомпилирована в каждый выпущенный образ, а ключ настройки запечатывает блок
# внутри него. Сменить их — значит, что КАЖДЫЙ уже работающий у клиента
# контейнер перестанет признавать наши лизы: «lease signature is not ours»,
# и чинится это только выкаткой нового образа всем.
#
# Поэтому сохраните вывод в менеджере паролей ПЕРЕД тем, как вставлять в
# GitHub: секреты GitHub нельзя прочитать обратно, а потеря ключа подписи
# означает, что новый образ не сможет обслуживать старых клиентов.
#
#   bash deploy/make-release-keys.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PY="$ROOT/prototype/.venv/bin/python"

[ -x "$PY" ] || { echo "нет $PY — соберите venv движка: cd prototype && python3 -m venv .venv && pip install -r requirements.txt"; exit 1; }

SIGNING="$("$PY" -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import sys; sys.path.insert(0, '$ROOT/prototype')
from licensing.keys import encode_private
print(encode_private(Ed25519PrivateKey.generate()))
")"
PUBLIC="$("$PY" -c "
import base64, sys; sys.path.insert(0, '$ROOT/prototype')
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from licensing.keys import encode_public
print(encode_public(Ed25519PrivateKey.from_private_bytes(base64.b64decode('$SIGNING')).public_key()))
")"
cat <<TEXT

════════════════════════════════════════════════════════════════════
  СОХРАНИТЕ ЭТО В МЕНЕДЖЕР ПАРОЛЕЙ ПРЯМО СЕЙЧАС.
  Обратно из секретов GitHub их прочитать нельзя.
════════════════════════════════════════════════════════════════════

  PSEUDEX_SIGNING_KEY
  $SIGNING


  Публичная половина (в секреты НЕ нужна, вкомпилируется сама):
  $PUBLIC

────────────────────────────────────────────────────────────────────
  Положить в секреты репозитория:

    gh secret set PSEUDEX_SIGNING_KEY --body '$SIGNING'

  И в deploy/.env на сервере — ТО ЖЕ значение: лицензионный сервер
  подписывает лизы этим ключом, а образ проверяет их вкомпилированной
  публичной половиной. Разойдутся — образ перестанет признавать наш сервер.
────────────────────────────────────────────────────────────────────
TEXT
