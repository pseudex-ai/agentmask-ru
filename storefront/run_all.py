"""Вся витрина одной командой, с честным разделением «прошло» и «не гонялось».

ЗАЧЕМ. Шесть проверок лежали рядом и не имели ни одного вызывающего — ровно та
болезнь, из-за которой `build_invoice` год не выставлял счетов. «Прогнали всё»
без списка означает «прогнали то, что вспомнили», а вспоминают не всё и не
всегда те же.

ПРОПУСК ПЕЧАТАЕТСЯ ОТДЕЛЬНОЙ КОЛОНКОЙ И НИКОГДА НЕ СЧИТАЕТСЯ ПРОХОЖДЕНИЕМ.
Две проверки требуют внешнего: `test_billing_e2e` — ключей боевого тестового
магазина ЮKassa, `test_billing_lifecycle` — поднятого стенда с контейнером. Без
них они не «зелёные» и не «красные», они НЕ ВЫПОЛНЯЛИСЬ, и итог обязан это
называть: батарея, в которой пропуск сливается с успехом, — это тот же ложный
зелёный, что гейт над пустым свидетельством.

    .venv/bin/python run_all.py               # всё, что доступно
    .venv/bin/python run_all.py --only 3      # один шаг по номеру
    .venv/bin/python run_all.py --strict      # пропуск = провал
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_DEPLOY = _HERE.parent / "deploy"
_PY = str(_HERE / ".venv" / "bin" / "python")


def _stand_up() -> bool:
    """Поднят ли локальный стенд. Спрашиваем, а не предполагаем."""
    tokens = _DEPLOY / ".local-tokens"
    if not tokens.exists():
        return False
    try:
        import httpx
    except ImportError:
        return False
    try:
        answer = httpx.get("http://127.0.0.1:9443/admin/list", timeout=3, headers={
            "Authorization": f"Bearer {tokens.read_text().splitlines()[0]}"})
    except Exception:  # noqa: BLE001 — любой отказ значит «не поднят»
        return False
    return answer.status_code == 200


def _has_yookassa() -> bool:
    return bool(os.environ.get("PSEUDEX_YOOKASSA_SECRET_KEY"))


# имя, файл, «можно ли сейчас», почему нельзя
# Линтер наших же проверок: запрещает `except`, гасящий провал. Живёт в движке,
# витрина входит в его область — поэтому и зовётся отсюда, его же питоном.
_LINT = ["python3", "e2e/lint_tests.py", ".", "licensing", "pseudex", "e2e",
         "../storefront"]

STEPS = [
    # ЛИНТЕР ТЕСТОВ ИДЁТ ПЕРВЫМ И ЖИВЁТ В ДВИЖКЕ. Он проверяет наши же проверки
    # на проглоченные провалы, и витрина входит в его область (`../storefront`),
    # но в этой батарее его не было — поэтому широкий `except`, гасивший провал,
    # доехал до CI и упал там, а не здесь. Проверка, которой нет локально, —
    # это проверка, про которую узнаёшь последним.
    ("00a-lint-tests", _LINT, lambda: True, ""),
    ("00-storefront", "test_storefront.py", lambda: True, ""),
    ("01-deploy-refs", "test_deploy_references.py",
     lambda: (_HERE.parent / "deploy").is_dir(),
     "нужен каталог deploy/ — он в закрытом репозитории рядом"),
    # БЕЛЫЙ СПИСОК РОБОТОВ ЖИВЁТ В deploy/, А ПРОВЕРЯЕТСЯ ЗДЕСЬ. Ошибка в нём
    # стоит в обе стороны и обе дорогие: строгий вариант отрезает поисковику
    # обход (сайта нет в выдаче), мягкий отдаёт сканеру лазейку мимо бана.
    ("01b-crawler-allowlist", "test_crawler_allowlist.py", lambda: True, ""),
    ("02-analytics", "test_analytics.py", lambda: True, ""),
    ("03-configurator", "test_configurator_renders.py", lambda: True, ""),
    ("04-ops-console", "test_ops_renders.py", lambda: True, ""),
    # ПРИБЛИЗИТЕЛЬНЫЙ ПОКАЗ ИНСТАНСОВ. Слот-машина (слоты/поколения/фенсинг)
    # удалена вместе с инстанс-лимитом (docs/tz-license-volume-quota.md §A);
    # осталась справка «инстансов в окне». Проверка сжата до юнит-теста
    # `billing/slots.py` — окружение движка ей больше не нужно.
    ("04l-slots", "test_slots.py", lambda: True, ""),
    ("04b-offers", "test_offers.py", lambda: True, ""),
    ("04c-hardcap", "test_hardcap.py", lambda: True, ""),
    ("04d-annual", "test_annual.py", lambda: True, ""),
    ("04e-auth-style", "test_auth_style.py", lambda: True, ""),
    ("04f-admin-2fa", "test_admin_2fa.py", lambda: True, ""),
    ("04g-passwordless", "test_passwordless.py", lambda: True, ""),
    ("04h-signup-forms", "test_signup_forms.py", lambda: True, ""),
    ("04i-paywall", "test_paywall.py", lambda: True, ""),
    # ОДИН РЯД, КОТОРОГО НЕТ НА ЛИЦЕНЗИОННОМ СЕРВЕРЕ, НЕ ОСТАНАВЛИВАЕТ ДЕНЬГИ.
    # 03.10.2026 `billing` был unhealthy на проде ровно поэтому, а в батарее не
    # было ничего, что гоняет `run_billing_cycle` до конца с таким рядом.
    ("04i2-refused-trial", "test_refused_trial_cycle.py", lambda: True, ""),
    ("04j-seo", "test_seo.py", lambda: True, ""),
    ("04k-yandex-api", "test_yandex_api.py", lambda: True, ""),
    ("05-billing-lifecycle", "test_billing_lifecycle.py", _stand_up,
     "нужен поднятый стенд: bash deploy/local.sh"),
    # НУЖНЫ ОБА, И ЭТО НЕ ПЕДАНТИЗМ. Проверка выпускает НАСТОЯЩИЙ ключ на
    # лицензионном сервере (клиент, которому ключа не выдавали, не может быть
    # ни остановлен, ни возобновлён), поэтому без стенда она падает сырой
    # трассировкой на 401 — а условие, спрашивавшее только про магазин,
    # пропускало её в такой прогон.
    ("06-billing-yookassa", "test_billing_e2e.py",
     lambda: _has_yookassa() and _stand_up(),
     "нужны ключи тестового магазина (source storefront/.env.dev) И "
     "поднятый стенд (bash deploy/local.sh)"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="",
                        help="запятыми: имена или их начала")
    parser.add_argument("--strict", action="store_true",
                        help="пропуск считать провалом")
    args = parser.parse_args()
    wanted = {part.strip() for part in args.only.split(",") if part.strip()}

    passed, failed, skipped = [], [], []
    started = time.monotonic()
    for name, script, available, why in STEPS:
        if wanted and not any(name.startswith(part) for part in wanted):
            continue
        if not available():
            print(f"ПРОПУСК  {name}  — {why}")
            skipped.append(name)
            continue
        began = time.monotonic()
        # ШАГ — ЭТО ЛИБО НАШ СКРИПТ, ЛИБО ГОТОВАЯ КОМАНДА. Линтер тестов лежит в
        # движке и запускается его питоном по другому корню, поэтому один
        # `[_PY, script]` на все шаги ему не годится.
        command = script if isinstance(script, list) else [_PY, script]
        where = _HERE.parent / "prototype" if isinstance(script, list) else _HERE
        result = subprocess.run(command, cwd=str(where))
        took = time.monotonic() - began
        if result.returncode == 0:
            print(f"OK    {name}  {took:.0f} с")
            passed.append(name)
        else:
            print(f"УПАЛО {name}  {took:.0f} с")
            failed.append(name)

    print("\n" + "=" * 62)
    print(f"прошло {len(passed)}, упало {len(failed)}, "
          f"НЕ ГОНЯЛОСЬ {len(skipped)} за {(time.monotonic() - started) / 60:.1f} мин")
    if failed:
        print(f"  УПАЛО: {failed}")
    if skipped:
        print(f"  НЕ ГОНЯЛОСЬ: {skipped} — это не «прошло»")
    # Ноль выполненных шагов — провал, а не чистый лист: так `--only` с
    # опечаткой превращался бы в зелёный прогон.
    if not passed and not failed:
        print("НИ ОДИН ШАГ НЕ ВЫПОЛНЯЛСЯ.")
        return 1
    return 1 if failed or (args.strict and skipped) else 0


if __name__ == "__main__":
    sys.exit(main())
