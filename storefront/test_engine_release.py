"""Какой образ сайт советует клиенту (D-061): плавающий минор из реестра версий.

Три источника правды в фиксированном порядке — override из окружения, файл
реестра, `latest` без файла — и перечитывание по mtime без рестарта. Каждый
случай был причиной реального дефекта 20.09.2026: тег `1.0.0`, вписанный
руками, которого в реестре не существовало.

    python3 test_engine_release.py
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="pseudex-engine-release-"))
    registry = tmp / "releases.json"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    os.environ["PSEUDEX_SECRET_KEY"] = "engine-release-test"
    os.environ["PSEUDEX_DEBUG"] = "1"
    os.environ["PSEUDEX_DB_PATH"] = str(tmp / "db.sqlite3")
    os.environ["SITE_URL"] = "http://localhost"
    os.environ["PSEUDEX_DOCKER_REPO"] = "cr.yandex/test/pseudex"
    os.environ["PSEUDEX_RELEASES_FILE"] = str(registry)
    os.environ.pop("PSEUDEX_DOCKER_IMAGE", None)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    call_command("migrate", verbosity=0, run_syncdb=True)
    call_command("seed_plans", verbosity=0)
    from storefront_web import engine_release

    failures: list[str] = []

    def check(name: str, held: bool, detail: str = "") -> None:
        print(f"{'PASS' if held else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
        if not held:
            failures.append(name)

    def write(cycle: str) -> None:
        doc = {"product": "pseudex", "schema": 1, "cycles": [{"cycle": cycle, "state": "current",
               "latest": {"version": f"{cycle}.0"}, "aliases": [cycle, "0", "latest"]}]}
        tmp_path = registry.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(doc), encoding="utf-8")
        os.replace(tmp_path, registry)

    check("без файла реестра сайт советует alias latest, не падает",
          engine_release.current_image() == "cr.yandex/test/pseudex:latest", engine_release.current_image())

    write("0.3")
    check("с реестром — плавающий минор новейшего цикла",
          engine_release.current_image() == "cr.yandex/test/pseudex:0.3", engine_release.current_image())

    time.sleep(0.01)
    write("0.4")
    check("замена файла видна без рестарта", engine_release.current_image() == "cr.yandex/test/pseudex:0.4",
          engine_release.current_image())

    registry.write_text("{broken", encoding="utf-8")
    check("битый файл — latest, не исключение", engine_release.current_image() == "cr.yandex/test/pseudex:latest",
          engine_release.current_image())

    settings.DOCKER_IMAGE = "cr.yandex/test/pseudex:0.9.9"
    check("override из окружения показывается как есть", engine_release.current_image() == "cr.yandex/test/pseudex:0.9.9")
    settings.DOCKER_IMAGE = ""

    # Витрина показывает то же, что отдаёт функция — через настоящий рендер.
    write("0.5")
    from django.test import Client
    html = Client().get("/").content.decode("utf-8")
    check("лендинг показывает тот же тег, что current_image()", "cr.yandex/test/pseudex:0.5" in html,
          "тег не найден в HTML лендинга")

    if failures:
        print(f"\n{len(failures)} провалено: {', '.join(failures)}")
        return 1
    print("\nобраз для клиента берётся из реестра версий")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
