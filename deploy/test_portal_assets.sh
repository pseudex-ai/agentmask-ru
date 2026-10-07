#!/bin/sh
# Наш знак на странице входа портала — БЕЗ DOCKER И БЕЗ PYTHON-ЗАВИСИМОСТЕЙ.
#
# ЗАЧЕМ ЭТОТ ФАЙЛ. Authelia не даёт подменить стили: портал вшит в её бинарник, и
# единственная штатная точка брендирования — `server.asset_path` с двумя файлами
# (`logo.png` и `favicon.ico`). Ломается это тихо и не там, где ждёшь:
#
#   1. правку шаблона забыли применить на стенде или наоборот — знак виден в
#      одном месте и не виден в другом;
#   2. файлы не примонтированы, и портал молча отдаёт свой стандартный значок;
#   3. растеризатор не запросил прозрачность — Chromium композитит скриншот на
#      белое, и наш знак приезжает на белом стикере. Именно это и случилось на
#      первом прогоне, и заметил это человек, а не проверка.
#
# Третий пункт и есть причина, по которой здесь строка про `omit_background`:
# файл с запечённым белым фоном выглядит корректным PNG и проходит любую
# проверку «файл существует».
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
TEMPLATE="$HERE/board/authelia/configuration.yml"
ASSETS="$HERE/board/authelia/assets"
PROD="$HERE/compose.yml"
STAND="$HERE/board/docker-compose.yml"
fail() { echo "FAIL $1"; exit 1; }

# 1. Шаблон указывает на каталог, который мы монтируем.
grep -q "asset_path: '/config/assets'" "$TEMPLATE" \
    || fail "в шаблоне портала нет asset_path: /config/assets"
echo "OK   шаблон портала указывает на /config/assets"

# 2. Оба места монтируют ИМЕННО этот каталог: стенд — чтобы правку знака было
#    видно локально, прод — чтобы её видели люди.
grep -q "./board/authelia/assets:/config/assets:ro" "$PROD" \
    || fail "в продовом compose каталог знака не примонтирован"
grep -q "./authelia/assets:/config/assets:ro" "$STAND" \
    || fail "в compose стенда каталог знака не примонтирован"
echo "OK   прод и стенд монтируют один и тот же каталог знака"

# 3. Файлы есть и они того рода, который ждёт Authelia.
[ -s "$ASSETS/logo.png" ] || fail "нет assets/logo.png"
[ -s "$ASSETS/favicon.ico" ] || fail "нет assets/favicon.ico"
case "$(file -b "$ASSETS/logo.png")" in
    *RGBA*|*"8-bit/color RGBA"*) : ;;
    *) fail "logo.png без альфа-канала — на тёмной карточке портала будет фон" ;;
esac
case "$(file -b "$ASSETS/favicon.ico")" in
    *"MS Windows icon resource"*"3 icons"*) : ;;
    *) fail "favicon.ico не многоразмерный (нужны 16/32/48)" ;;
esac
echo "OK   logo.png с прозрачностью и многоразмерный favicon.ico"

# 4. Растеризатор просит прозрачность ЯВНО — иначе Chromium запекает белое.
grep -q "omit_background=True" "$HERE/board/authelia/make-assets.py" \
    || fail "make-assets.py не запрашивает omit_background: знак приедет на белом фоне"
echo "OK   растеризатор знака не запекает фон"

# 5. Источник знака один: файлы выведены из векторов витрины, а не нарисованы
#    отдельно — иначе знак на сайте и знак на входе разойдутся.
grep -q "storefront" "$HERE/board/authelia/make-assets.py" \
    || fail "make-assets.py не берёт вектор из витрины"
[ -s "$ROOT/storefront/static/logo.svg" ] || fail "нет вектора витрины storefront/static/logo.svg"
[ -s "$ROOT/storefront/static/favicon.svg" ] || fail "нет вектора витрины storefront/static/favicon.svg"
echo "OK   знак портала выведен из векторов витрины"

echo "deploy/test_portal_assets.sh: знак портала подключён целиком"
