"""ИНСТАНСЫ — ПРИБЛИЗИТЕЛЬНАЯ СПРАВКА, И «НЕ НАЗВАЛ» — ЭТО НЕ НОЛЬ.

Слот/поколение/эпоха/фенсинг удалены (docs/tz-license-volume-quota.md §A): счёт
инстансов как ЛИМИТ убран — весь трафик через один прокси его обходил, а детектор
отказов нереализуем (Chandra–Toueg), и шесть заходов доказали это на живых
клиентах. Принуждение теперь объёмное (period-квота + абсолютный потолок
запросов). От инстансов на экранах осталась одна справка: сколько РАЗЛИЧНЫХ
инстансов сервер видел в окне.

Эта проверка пиновала прежнюю слот-машину целиком (плашки, поколения, фенсинг,
снятое тело настоящего сервера). Машины больше нет, поэтому проверка сжата до
единственного, что осталось у витрины и что ещё можно сломать: приблизительного
показа. Один урок машину пережил — число, которого сервер не назвал, обязано
доехать молчанием, а не нулём: «0 инстансов» при живых арендах читается как
ответ «ничего не работает».

    cd storefront && .venv/bin/python test_slots.py
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


def main() -> int:
    sys.path.insert(0, str(_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    from billing import slots

    # --- приблизительный показ: сервер назвал число ---
    view = slots.describe({"instances": 3}, 0.0)
    check("известное число инстансов доезжает как есть",
          view["known"] is True and view["instances"] == 3,
          f"{view!r}")

    # Прежнее имя поля сервера тоже принимается — витрина и сервер могут ехать
    # не одномоментно, и `occupied` — это тот же счётчик под старым именем.
    legacy = slots.describe({"occupied": 2}, 0.0)
    check("прежнее имя поля (`occupied`) читается тем же числом",
          legacy["instances"] == 2, f"{legacy!r}")

    # --- «не назвал» — это НЕ ноль ---
    silent_field = slots.describe({}, 0.0)
    check("число, которого сервер не назвал, — None, а не 0",
          silent_field["known"] is True and silent_field["instances"] is None,
          f"{silent_field!r}")

    # Список сырых аренд (форма `/admin/usage`) — не число инстансов: молчание.
    raw = slots.describe({"instances": [{"instance_id": "a"}, {"instance_id": "b"}]}, 0.0)
    check("список сырых аренд не считается числом инстансов",
          raw["instances"] is None, f"{raw!r}")

    # bool — не число: True не должен стать «1 инстанс».
    boolean = slots.describe({"instances": True}, 0.0)
    check("булево значение не выдаётся за число инстансов",
          boolean["instances"] is None, f"{boolean!r}")

    # --- молчание сервера ---
    down = slots.unknown()
    check("молчание сервера — это «неизвестно», а не ноль",
          down["known"] is False and down["instances"] is None,
          f"{down!r}")

    print("\n" + ("ВСЁ ЗЕЛЁНОЕ" if not FAILURES else f"УПАЛО: {FAILURES}"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
