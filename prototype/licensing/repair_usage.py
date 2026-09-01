"""Починить строки `usage`, записанные до того, как вход стал проверяться.

    python3 -m licensing.repair_usage                 # показать, что найдено
    python3 -m licensing.repair_usage --apply         # переписать

ЗАЧЕМ ОТДЕЛЬНЫЙ СКРИПТ, А НЕ МИГРАЦИЯ НА СТАРТЕ. Ровно та же причина, по
которой `deploy/backup.sh` запускается руками: это правка биллинговых данных
клиента, и она обязана быть решением человека, с выводом до и после, а не
побочным эффектом выкатки.

Что чинится. Значение внутри `entities` могло быть чем угодно, и нечисловое
роняло `usage_totals` в `TypeError` — то есть `/admin/usage` отдавал 500
НАВСЕГДА для этой организации, а вместе с ним переставали работать кабинет и
выставление счёта. Чтение теперь такие значения пропускает и продолжает, так
что ручка поднимается сразу; этот скрипт убирает мусор из хранения, чтобы
предупреждение не сыпалось в лог вечно.

Счётчики (`requests`, `values`) НЕ трогаются. Отрицательное значение могло быть
записано только подписанным отчётом, то есть это спор о деньгах, а не мусор, и
править его молча нельзя — он печатается, чтобы разговор был предметным.
"""

import json
import os
import sys

from licensing.store import LicenseStore


def main() -> int:
    apply = "--apply" in sys.argv
    store = LicenseStore(os.environ.get("PSEUDEX_LICENSE_DB", "license.db"))
    rows = store._fetchall(  # noqa: SLF001 — разовый инструмент над своим же store
        "SELECT org_id, instance_id, entities, requests, values_total FROM usage", ())
    broken, negative = [], []
    for org_id, instance_id, entities, requests, values_total in rows:
        if int(requests or 0) < 0 or int(values_total or 0) < 0:
            negative.append((org_id, instance_id, requests, values_total))
        try:
            stored = json.loads(entities or "{}")
        except ValueError:
            broken.append((org_id, instance_id, entities, {}))
            continue
        clean = {name: count for name, count in stored.items()
                 if isinstance(count, int) and not isinstance(count, bool) and count >= 0}
        if clean != stored:
            broken.append((org_id, instance_id, entities, clean))

    for org_id, instance_id, before, after in broken:
        print(f"entities  {org_id}/{instance_id}: {str(before)[:60]} -> {after}")
    for org_id, instance_id, requests, values_total in negative:
        print(f"ОТРИЦАТЕЛЬНЫЕ СЧЁТЧИКИ  {org_id}/{instance_id}: "
              f"requests={requests} values_total={values_total} — НЕ ТРОГАЮ, "
              f"это спор о деньгах, а не мусор")

    if not broken and not negative:
        print("нечего чинить")
        return 0
    if not broken:
        print("\nмусора в entities нет, чинить нечего.")
        return 0
    if not apply:
        print(f"\nнайдено строк с мусором в entities: {len(broken)}. "
              f"Перезапустите с --apply, чтобы переписать.")
        return 0
    for org_id, instance_id, _before, after in broken:
        with store._lock:  # noqa: SLF001
            store._conn.execute(
                "UPDATE usage SET entities=? WHERE org_id=? AND instance_id=?",
                (json.dumps(after), org_id, instance_id))
            store._conn.commit()
    print(f"\nпереписано строк: {len(broken)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
