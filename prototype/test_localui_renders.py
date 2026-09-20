"""Открыть интерфейс НАСТОЯЩИМ браузером и посмотреть, что он нарисовал.

ПОЧЕМУ ЭТОГО НЕ ЗАМЕНЯЕТ НИ ОДИН HTTP-ТЕСТ. В этом репозитории уже было ровно
так: страница отдавала 200, ассеты отдавали 200, заголовок CSP совпадал с
ожидаемым — и не исполнялся НИ ОДИН скрипт, потому что `script-src 'self'`
блокировал import map, модульный граф не разрешался, и страница рендерилась
ПУСТОЙ. Записано в `localui/server.py`: «заголовок — не доказательство того, что
страница работает». Проверить это можно единственным способом — открыть.

ПРОПУСК ЗДЕСЬ — ЭТО ПРОВАЛ, А НЕ «НЕ СМОГЛИ». Отсутствие playwright печатает
команду установки и выходит НЕНУЛЁМ: проверка, которая при нехватке зависимости
тихо зеленеет, — это тот самый ложный зелёный, ради которого весь этот файл и
заведён. `pip install playwright && python -m playwright install chromium`.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_PORT = int(os.environ.get("PSEUDEX_RENDER_PORT", "8391"))
_TOKEN = "render-check-token"
# СТАВИТСЯ НАМИ, ЧТОБЫ ПРОВЕРКА НИЖЕ МОГЛА УПАСТЬ. Интерфейс наследует окружение
# и с этим значением работает как в бою; экран обязан его не показать.
_GATEWAY_TOKEN = "gateway-token-that-must-not-be-rendered"

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def _start_ui() -> subprocess.Popen:
    env = dict(os.environ)
    env.update({"PSEUDEX_UI_TOKEN": _TOKEN, "PSEUDEX_UI_PORT": str(_PORT),
                "PSEUDEX_GATEWAY_TOKEN": _GATEWAY_TOKEN,
                "PSEUDEX_DB_DIR": tempfile.mkdtemp(prefix="pseudex-render-")})
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "pseudex.localui.server:app",
         "--port", str(_PORT), "--host", "127.0.0.1"],
        cwd=str(_ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{_PORT}/", timeout=2)
            return server
        except urllib.error.HTTPError:
            return server          # отвечает — этого достаточно
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("интерфейс не поднялся")


def _launch(pw):
    """Chromium штатный, а если версия сборки не та — тот, что лежит рядом.

    Playwright жёстко связывает пакет с НОМЕРОМ сборки браузера, и в готовом
    образе (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`) лежит другой номер:
    штатный запуск отправляет ставить браузер, которого качать не надо и,
    возможно, нельзя. Проверка, падающая на несовпадении номеров, перестаёт
    бежать — а падать она должна на интерфейсе.
    """
    try:
        return pw.chromium.launch()
    except Exception as error:                      # noqa: BLE001 — любая
        root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
        found = sorted(Path(root).glob("chromium-*/chrome-linux/chrome")) if root else []
        if not found:
            raise RuntimeError(
                f"chromium не запускается ({error}); поставьте его "
                f"`python -m playwright install chromium` или укажите "
                f"PLAYWRIGHT_BROWSERS_PATH") from error
        return pw.chromium.launch(executable_path=str(found[-1]))


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright не установлен, а без него эта проверка ничего не "
              "проверяет:\n  pip install playwright && "
              "python -m playwright install chromium", file=sys.stderr)
        raise SystemExit(2) from None

    server = _start_ui()
    try:
        with sync_playwright() as pw:
            browser = _launch(pw)
            page = browser.new_page()
            # СТРАНИЦА, КОТОРАЯ БРОСИЛА ИСКЛЮЧЕНИЕ ИЛИ БЫЛА ЗАРЕЗАНА CSP, ДЛЯ
            # HTTP ВЫГЛЯДИТ ТОЧНО ТАК ЖЕ, как работающая. Отсюда и слушатели.
            broken: list[str] = []
            page.on("pageerror", lambda error: broken.append(f"pageerror: {error}"))
            page.on("console", lambda message: broken.append(f"console: {message.text}")
                    if "Content Security Policy" in message.text else None)

            page.goto(f"http://127.0.0.1:{_PORT}/?secret={_TOKEN}",
                      wait_until="networkidle")
            page.wait_for_timeout(1500)

            tabs = page.locator("nav button").all_inner_texts()
            check("страница вообще отрисовалась", len(tabs) >= 7, str(tabs))
            check("ни одной ошибки исполнения и ни одного запрета CSP",
                  not broken, "; ".join(broken[:3]))

            if any("ИНТЕГРАЦИЯ" in tab for tab in tabs):
                page.get_by_role("button", name="ИНТЕГРАЦИЯ").click()
                page.wait_for_timeout(600)
                body = page.inner_text("body")
                # ВАЖНЕЙШЕЕ МЕСТО ИНТЕГРАЦИИ, по формулировке спецификации: шлюз,
                # пропускающий запрос при 503, обнуляет защиту молча.
                check("экран называет fail-closed прямо",
                      "БЛОКИРОВАТЬ ЗАПРОС" in body)
                check("и предупреждает про аргументы инструментов",
                      "unmask_arguments" in body)
                # СЧИТАТЬ ЭЛЕМЕНТЫ МАЛО: пустой <pre> — это ровно то, как
                # выглядит фрагмент, чей шаблон развалился, а элемент при этом
                # есть. Читается ТЕКСТ, и в нём — то, что делает фрагмент
                # рабочим.
                bodies = page.locator(".snip pre").all_inner_texts()
                check("фрагментов не меньше шести и все непустые",
                      len(bodies) >= 6 and all(len(t) > 80 for t in bodies),
                      f"{len(bodies)}: {[len(t) for t in bodies]}")
                # УТВЕРЖДЕНИЯ НА КОДЕ, А НЕ НА СЛОВАХ РЯДОМ С НИМ. Первая
                # версия искала «CustomLogger» где угодно во фрагменте — и
                # проходила по КОММЕНТАРИЮ, объясняющему, зачем нужен
                # CustomLogger, даже когда сам класс был выброшен. Проверено
                # откатом: ни один негативный прогон её не уронил.
                joined = "\n".join(bodies)
                check("хук LiteLLM показан как метод CustomLogger, а не функция",
                      "class Pseudex(CustomLogger):" in joined
                      and "    async def async_pre_call_hook(" in joined,
                      "модульная функция не вызывается LiteLLM никогда — "
                      "ни ошибки, ни маскирования")
                check("обратное плечо на месте",
                      "    async def async_post_call_success_hook(" in joined
                      and "residual_tokens" in joined,
                      "без него подстановки уезжают в инструменты вместо значений")
                check("/unmask показан с полем response, а не text",
                      '"response": response.model_dump()' in joined
                      and '"response": {"choices"' in joined
                      and '"text":' not in joined,
                      "service.py читает body['response'] и 400 на всём остальном")

                # КАЖДОЕ ТЕЛО `curl -d` РАЗБИРАЕТСЯ КАК JSON, И ЭТО НЕ
                # ПРИДИРКА К ОФОРМЛЕНИЮ. Фрагмент здесь — не иллюстрация, его
                # копируют и выполняют. Экранирование внутри шаблонной строки
                # раскрывается ДВАЖДЫ (питон, писавший файл, и JS, читающий
                # шаблон), и на экране уже оказывалось `["{"phone": …}"]` —
                # выглядит правдоподобно и не разбирается ничем.
                bad = []
                for payload in re.findall(r"-d '(\{.*?\})'", joined, re.S):
                    try:
                        outer = json.loads(payload)
                    except ValueError as error:
                        bad.append(f"внешний: {error}")
                        continue
                    for argument in outer.get("arguments", []):
                        try:
                            json.loads(argument)
                        except ValueError as error:
                            bad.append(f"внутренний: {error}")
                check("каждое тело curl на экране разбирается как JSON",
                      not bad, "; ".join(bad[:2]))

                # ТОКЕН ШЛЮЗА НА ЭКРАНЕ НЕ ПОЯВЛЯЕТСЯ: интерфейс держит ДРУГОЙ
                # токен, и разделение этих двух — не оформление.
                #
                # ПРОВЕРЯЕТСЯ ЗНАЧЕНИЕ, КОТОРОЕ ТОЧНО СУЩЕСТВУЕТ. Раньше здесь
                # читалась переменная, которую не ставит ни тест, ни CI, — то
                # есть утверждалось отсутствие строки «нет-такого». Проверка,
                # которая не может упасть, — ровно тот ложный зелёный, ради
                # которого написан весь этот файл.
                check("значение токена шлюза не показано",
                      _GATEWAY_TOKEN not in body, "и это не пустая строка")
            else:
                check("вкладка ИНТЕГРАЦИЯ есть", False, str(tabs))
            browser.close()
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
    print("интерфейс OK — страница исполняется, CSP ничего не режет, экран "
          "интеграции нарисован")


if __name__ == "__main__":
    main()
