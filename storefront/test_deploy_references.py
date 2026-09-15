"""Имена, которые скрипты деплоя называют в SQL, против настоящих таблиц.

ЗАЧЕМ. `restore-drill.sh` спрашивал `SELECT count(*) FROM billing_organization`.
Такой таблицы нет: `Organization` живёт в приложении `accounts`, значит таблица
называется `accounts_organization`. Запрос падал, `|| echo 0` давал ноль, и
учения по восстановлению объявляли ПУСТЫМ каждый исправный бэкап — то есть
единственная проверка восстановимости была постоянно красной, а постоянно
красная тревога учит мьютить канал.

Опечатку такого рода нельзя увидеть чтением: имя правдоподобно, ошибка на одно
слово, а падение выглядит как настоящая находка. Зато она проверяется за
миллисекунду, если спросить сами модели.

ПОЧЕМУ ЗДЕСЬ, А НЕ В `deploy/`. Имя таблицы знает Django, и знает его только
через модели. Скрипт на shell спросить их не может; этот файл может.

    cd storefront && .venv/bin/python test_deploy_references.py
"""

import os
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_DEPLOY = _HERE.parent / "deploy"

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ.setdefault("PSEUDEX_SECRET_KEY", "deploy-refs")
    os.environ.setdefault("PSEUDEX_DB_PATH", "/tmp/pseudex-deploy-refs.sqlite3")
    import django
    django.setup()
    from django.apps import apps

    tables = {model._meta.db_table for model in apps.get_models()}
    check("модели прочитаны", len(tables) > 5, f"{len(tables)} таблиц")

    scripts = sorted(_DEPLOY.glob("*.sh"))
    check("скрипты деплоя на месте", bool(scripts), f"{len(scripts)} шт")

    referenced: list[tuple[str, str]] = []
    for script in scripts:
        text = script.read_text(encoding="utf-8")
        # Только то, что реально исполняется как SQL по нашей базе. Слова из
        # комментариев берутся тоже — и это НАМЕРЕННО: комментарий, называющий
        # несуществующую таблицу, врёт следующему читателю ровно так же.
        #
        # НО НЕ DOCKERFILE `FROM`. Скрипт сборки образа несёт в heredoc
        # `FROM debian:trixie-slim` — это базовый образ, не таблица, и regex
        # `FROM слово` ловил его как несуществующую таблицу «debian» (ложный
        # красный). Два признака Docker-директивы, любой исключает: за именем
        # идёт `:` (тег образа) или `FROM` стоит в начале строки (директива, а
        # не `SELECT … FROM`). SQL-имя таблицы не бывает ни тем, ни другим —
        # `SELECT count(*) FROM accounts_organization` остаётся пойманным.
        for match in re.finditer(r"\bFROM\s+([a-z_][a-z0-9_]*)", text):
            if text[match.end():match.end() + 1] == ":":
                continue
            line_start = text.rfind("\n", 0, match.start()) + 1
            if text[line_start:match.start()].strip() == "":
                continue
            referenced.append((script.name, match.group(1)))

    check("в скриптах вообще нашлись обращения к таблицам", bool(referenced),
          f"{len(referenced)} шт — если ноль, проверка ничего не проверяет")

    # ПОЛОЖИТЕЛЬНЫЙ КОНТРОЛЬ. Без него пустой список ссылок читался бы как
    # «все имена верны» — та же ошибка, что и в проверяемом скрипте.
    if not referenced:
        return 1

    unknown = [(script, table) for script, table in referenced
               if table not in tables]
    check("каждое имя таблицы существует", not unknown,
          "; ".join(f"{s}: {t}" for s, t in unknown) or
          f"проверено {len(referenced)}: {sorted({t for _, t in referenced})}")

    # --- ВТОРАЯ БАЗА, ВТОРАЯ СХЕМА, ТА ЖЕ ОШИБКА ---------------------------
    #
    # Лицензионная база — не Django: это SQLite лицензионного сервера, и её
    # таблицы знает только `licensing/store.py`. К ней обращается воркфлоу
    # `backup-audit`, который ВОССТАНАВЛИВАЕТ копию и считает в ней строки, —
    # то есть единственное место, где проверяется, что бэкап вообще
    # разворачивается. Опечатка в имени таблицы там означает вечно красную
    # проверку бэкапов, а вечно красная проверка учит мьютить канал: ровно то,
    # ради чего написан этот файл.
    store = (_HERE.parent / "prototype" / "licensing" / "store.py").read_text(encoding="utf-8")
    license_tables = set(re.findall(r"CREATE TABLE IF NOT EXISTS ([a-z_]+)", store))
    check("схема лицензионной базы прочитана", len(license_tables) > 3,
          f"{len(license_tables)} таблиц: {sorted(license_tables)}")

    audit = _HERE.parent / ".github" / "workflows" / "backup-audit.yml"
    check("воркфлоу проверки бэкапов на месте", audit.exists(), str(audit))
    if audit.exists():
        asked = re.findall(r"\bFROM\s+([a-z_][a-z0-9_]*)", audit.read_text(encoding="utf-8"))
        check("воркфлоу вообще о чём-то спрашивает базу", bool(asked),
              f"{len(asked)} шт — если ноль, восстановление ничего не проверяет")
        strangers = [t for t in asked if t not in license_tables]
        check("и спрашивает существующие таблицы", not strangers,
              ", ".join(strangers) or f"проверено {sorted(set(asked))}")

    print()
    if FAILURES:
        print(f"{len(FAILURES)} провалено: {', '.join(FAILURES)}")
        return 1
    print("скрипты деплоя называют существующие таблицы")
    return 0


if __name__ == "__main__":
    sys.exit(main())
