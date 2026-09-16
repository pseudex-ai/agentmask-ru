"""Конфигуратор в НАСТОЯЩЕМ браузере: вердикт считается в JS.

ПОЧЕМУ ЭТОГО НЕ ЗАМЕНЯЕТ `test_storefront.py`. Тот проверяет, что блок
отрендерен и что ручка спроса ведёт себя правильно, — и оба утверждения
остались бы верными, если бы `landing.js` бросал исключение на первой строке.
Вердикт — «находим» или «в разработке» — вычисляется в браузере, и страница,
отдавшая 200 с мёртвым скриптом, выглядит для HTTP точно так же, как рабочая.
Этот репозиторий уже платил ровно этим: локальный интерфейс отдавал 200 на всё
и не исполнял ни одного скрипта, потому что CSP резал import map.

ПРОПУСК ЗДЕСЬ — ПРОВАЛ, А НЕ «НЕ СМОГЛИ»: отсутствие playwright печатает
команду установки и выходит ненулём.
"""

import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_PORT = int(os.environ.get("PSEUDEX_CFG_PORT", "8412"))
# ОДИН ПУТЬ К БАЗЕ НА ВЕСЬ ПРОГОН. Он создавался внутри `_start_site`, и подсчёт
# строк потом смотрел в ДРУГУЮ базу — то есть проверка «заявка доехала» читала
# пустой файл и была бы красной всегда, а на зелёной ветке — бессмысленной.
_DB = os.path.join(tempfile.mkdtemp(prefix="pseudex-cfg-db-"), "store.sqlite3")

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def _launch(pw):
    """Chromium штатный, а если номер сборки не тот — тот, что лежит рядом.

    Тот же приём, что в `prototype/test_localui_renders.py`: playwright жёстко
    связывает пакет с номером сборки браузера, и в готовом образе лежит другой.
    Проверка, падающая на несовпадении номеров, перестаёт бежать — а падать она
    должна на конфигураторе.
    """
    try:
        return pw.chromium.launch()
    except Exception as error:                      # noqa: BLE001 — любая
        root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
        found = sorted(Path(root).glob("chromium-*/chrome-linux/chrome")) if root else []
        if not found:
            raise RuntimeError(
                f"chromium не запускается ({error}); поставьте его "
                f"`python -m playwright install chromium`") from error
        return pw.chromium.launch(executable_path=str(found[-1]))


def _start_site() -> subprocess.Popen:
    env = dict(os.environ)
    env.update({
        "DJANGO_SETTINGS_MODULE": "pseudex_site.settings",
        "PSEUDEX_DEBUG": "1",
        "PSEUDEX_SECRET_KEY": "test-only",
        "PSEUDEX_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "PSEUDEX_DB_PATH": _DB,
    })
    subprocess.run([sys.executable, "manage.py", "migrate", "--noinput", "-v", "0"],
                   cwd=str(_ROOT), env=env, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([sys.executable, "manage.py", "seed_plans", "-v", "0"],
                   cwd=str(_ROOT), env=env, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{_PORT}",
         "--noreload", "--insecure"],
        cwd=str(_ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{_PORT}/", timeout=2)
            return server
        except urllib.error.HTTPError:
            return server
        except OSError:
            time.sleep(0.5)
    server.terminate()
    raise RuntimeError("витрина не поднялась")


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright не установлен, а без него эта проверка ничего не "
              "проверяет:\n  pip install playwright && "
              "python -m playwright install chromium", file=sys.stderr)
        raise SystemExit(2) from None

    sys.path.insert(0, str(_ROOT))
    from storefront_web import detection_types

    gap = next(group for group in detection_types.GROUPS if not group.get("found"))
    covered = next(group for group in detection_types.GROUPS if group.get("found"))
    medical = next(group for group in detection_types.GROUPS
                   if group["code"] == "medical")

    server = _start_site()
    try:
        with sync_playwright() as pw:
            browser = _launch(pw)
            page = browser.new_page()
            broken: list[str] = []
            page.on("pageerror", lambda error: broken.append(f"pageerror: {error}"))
            page.on("console", lambda message: broken.append(f"csp: {message.text}")
                    if "Content Security Policy" in message.text else None)

            page.goto(f"http://127.0.0.1:{_PORT}/#configurator", wait_until="networkidle")
            page.wait_for_timeout(800)
            check("ни одной ошибки исполнения и ни одного запрета CSP",
                  not broken, "; ".join(broken[:2]))

            out = page.locator("#cfg-out")
            check("до выбора вердикта нет", out.is_hidden())

            # ПОКРЫТАЯ ГРУППА: ритейл обязан читаться как выполненная работа, а
            # не как отсутствие проблемы (ТЗ вертикалей §2).
            page.locator(f'input[data-group="{covered["code"]}"]').check()
            page.wait_for_timeout(300)
            text = out.inner_text()
            check("отмеченная покрытая группа даёт вердикт «находим»",
                  not out.is_hidden() and "НАХОДИМ" in text, text[:120])
            check("и говорит, что докупать нечего",
                  "докупать ничего не нужно" in page.locator("#cfg-note").inner_text())
            check("кнопки заявки при этом нет",
                  page.locator("#cfg-send").is_hidden())

            page.locator(f'input[data-group="{gap["code"]}"]').check()
            page.wait_for_timeout(300)
            check("непокрытая группа даёт «в разработке»",
                  "В РАЗРАБОТКЕ" in out.inner_text(), out.inner_text()[:120])
            check("и кнопка заявки появляется",
                  page.locator("#cfg-send").is_visible())

            page.locator(f'input[data-group="{medical["code"]}"]').check()
            page.wait_for_timeout(300)
            check("медицина отвечает СВОЕЙ причиной, а не общим отказом",
                  "СТАТЬЕ 10" in out.inner_text().upper(), out.inner_text()[-160:])

            # ОТПРАВКА ИДЁТ ДО СЕРВЕРА И ЗАПИСЫВАЕТСЯ. Кнопка, говорящая
            # «записали» без записи, — тот же промах, что «СКОПИРОВАНО» при
            # недоступном буфере обмена.
            page.locator("#cfg-send").click()
            page.wait_for_timeout(1200)
            note = page.locator("#cfg-note").inner_text()
            check("после отправки страница говорит, что записала",
                  "Записали" in note, note[:120])

            # СНИМОК — В ВРЕМЕННЫЙ КАТАЛОГ, а не в дерево: артефакт прогона в
            # корне репозитория попадает в чей-нибудь `git add -A`.
            shot = Path(tempfile.gettempdir()) / "pseudex-configurator.png"
            page.screenshot(path=str(shot), full_page=False)
            print(f"  снимок: {shot}")
            browser.close()

        browser_wrote = _rows_written()
        check("и в базе появились строки спроса", browser_wrote > 0,
              f"строк {browser_wrote}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} — {', '.join(FAILURES)}")
        raise SystemExit(1)
    print("конфигуратор OK — вердикт считается в браузере, заявка доезжает до базы")


def _rows_written() -> int:
    """Строки спроса из базы, в которую писал поднятый сервер.

    В ОТДЕЛЬНОМ ПРОЦЕССЕ: этот интерпретатор Django не настраивал, а настроить
    его на середине прогона значило бы держать два подключения к одному SQLite
    ради одного числа.
    """
    done = subprocess.run(
        [sys.executable, "manage.py", "shell", "-c",
         "from ops.models import DemandDay; print(DemandDay.objects.count())"],
        cwd=str(_ROOT), env={**os.environ,
                             "DJANGO_SETTINGS_MODULE": "pseudex_site.settings",
                             "PSEUDEX_SECRET_KEY": "test-only",
                             "PSEUDEX_DB_PATH": _DB},
        capture_output=True, text=True, timeout=120)
    try:
        return int((done.stdout or "0").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return 0


if __name__ == "__main__":
    main()
