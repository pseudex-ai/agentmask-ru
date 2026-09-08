"""Числа, которые мы ПЕЧАТАЕМ клиенту, против чисел, по которым работаем.

ЗАЧЕМ. Обещание живёт в русской прозе на лендинге, а механизм — в питоне
движка, в другом каталоге и под другим venv. Сверять их было некому, и оба
известных расхождения нашлись глазами, а не проверкой: лендинг обещал
тарификацию по объёму, которой в коде не было вовсе, и «48 часов при неоплате»,
которые описывали не тот факт — 48 часов это запас аренды при НАШЕЙ
недоступности, а неплательщика останавливает срок счёта плюс грация.

НАПРАВЛЕНИЕ ПРОВЕРКИ — ОТ КОДА К ТЕКСТУ, и это не формальность: числа решаются
здесь, в движке, а страница их пересказывает. Поэтому файл лежит в
`prototype/`, читает шаблон витрины как ДАННЫЕ и не импортирует из неё ничего —
запрет `pseudex` -> `licensing` остаётся в силе, а `storefront` вообще другой
питон.

ЧЕГО ЗДЕСЬ НЕТ. Утверждений, которые нельзя проверить вычислением: расход
памяти и задержка — это ЗАМЕРЫ, и их место в отчёте о замере, а не в сравнении
констант. Сверять замер с константой значило бы выдать одно за другое.

    python3 test_published_claims.py
"""

import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_LANDING = _ROOT.parent / "storefront" / "templates" / "landing.html"

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def _defaults() -> dict[str, int]:
    """Значения по умолчанию лицензионного сервера, БЕЗ его импорта.

    Импорт поднял бы `LicenseStore` и открыл базу — сервер не библиотека. Нас
    интересуют ровно литералы по умолчанию, и они читаются как текст.
    """
    source = (_ROOT / "licensing" / "server.py").read_text(encoding="utf-8")
    found = {}
    for name, variable in (("ttl", "PSEUDEX_LEASE_TTL_SECONDS"),
                           ("grace", "PSEUDEX_GRACE_SECONDS")):
        match = re.search(rf'os\.environ\.get\("{variable}",\s*"(\d+)"\)', source)
        if match:
            found[name] = int(match.group(1))
    return found


def main() -> int:
    if not _LANDING.exists():
        print(f"нет {_LANDING} — витрина не на месте")
        return 1
    landing = _LANDING.read_text(encoding="utf-8")
    defaults = _defaults()

    check("значения по умолчанию найдены в сервере",
          {"ttl", "grace"} <= set(defaults), str(sorted(defaults)))
    if {"ttl", "grace"} - set(defaults):
        return 1

    # --- срок аренды ----------------------------------------------------
    ttl_hours = defaults["ttl"] / 3600
    says_daily = "Аренда суточная" in landing
    check("страница называет аренду суточной ровно когда она суточная",
          says_daily == (ttl_hours == 24), f"TTL={ttl_hours:.0f} ч, текст={says_daily}")

    # --- запас при нашей недоступности ----------------------------------
    grace_hours = defaults["grace"] / 3600
    published = {int(value) for value in re.findall(r"(\d+) часов", landing)}
    check("опубликованный запас равен настоящему",
          int(grace_hours) in published,
          f"grace={grace_hours:.0f} ч, на странице: {sorted(published)}")

    # --- срок оплаты и грация приходят ИЗ КОДА, а не литералом ----------
    # Их значения живут в `billing/services.py`, поэтому здесь проверяется не
    # число, а то, что страница его не выдумывает: литерал в прозе разъедется
    # молча, а переменная шаблона — нет.
    # `metered_floor` больше не одно число на всю страницу: порог свой у каждого
    # тарифа и печатается в карточке из строки БД. Проверяем, что печатается
    # именно поле тарифа, а не literal.
    for token in ("{{ due_days }}", "{{ grace_days }}", "plan.metered_floor",
                  "plan.metered_per_1k", "plan.included_requests"):
        check(f"страница берёт {token} из кода", token in landing)

    # --- и ни одного оставшегося литерала на месте этих чисел -----------
    # «300 000» в прозе означало бы вторую копию порога.
    stale = [needle for needle in ("300 000 запросов", "7 дней", "3 дня",
                                  "{{ metered_floor }}")
             if needle in landing]
    check("старые литералы этих сроков со страницы убраны", not stale, str(stale))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} провалено: {', '.join(FAILURES)}")
        return 1
    print("напечатанное клиенту совпадает с тем, по чему работает движок")
    return 0


if __name__ == "__main__":
    sys.exit(main())
