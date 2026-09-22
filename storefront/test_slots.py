"""ЭКРАН, КОТОРЫЙ ВРЁТ ПРО СЛОТ, — ЭТО ТОТ ЖЕ ДЕФЕКТ, ЧТО И СЛОТ, КОТОРЫЙ ДЕРЖИТ ТРУП.

Что здесь доказывается (Б26bis, `research/2026-09-22-instance-liveness-and-slots.md` §6):

  * «занято» — это ЧИСЛО С СЕРВЕРА, а не длина списка. В списке
    `/admin/instances` теперь есть и `silent`, и `released` — контейнеры,
    которые слот НЕ держат; кабинет показывал бы «3 из 1 занято» человеку, у
    которого занят один, а консоль — превышение тарифа, которого нет;
  * три состояния РАЗЛИЧИМЫ на вид. Единственная ветка старого шаблона была
    `cooling`, и всё остальное красилось зелёным «ДЕРЖИТ СЛОТ» — включая
    контейнер, который мы сами признали замолчавшим;
  * экран называет ДЕЙСТВИЕ: упавший контейнер освобождает слот через
    `alive_seconds` молчания, переразвёртывание на том же томе не теряет его
    вовсе;
  * молчание лицензионного сервера показано молчанием, а не нулём: «0 из 1
    занято» читается как ответ, и человек делает из него вывод, что
    контейнеров у него нет.

КАК. Лицензионный сервер подменён заглушкой ПО HTTP, а не функцией: предмет
проверки — цепочка «ответ ручки → коннектор → вьюха → шаблон», и подменённая
`licensing.instances` вырезала бы из неё коннектор, то есть ровно то место, где
поле `occupied` может потеряться. Сами состояния и занятость считает движок
(`licensing/store.py::_occupancy`), и пинит их его же набор — здесь заглушка
задаёт ответ, а не повторяет его арифметику.

НАСТОЯЩИЙ БРАУЗЕР, как у остальных отрисовочных проверок витрины
(`test_ops_renders.py`, `test_configurator_renders.py`): 200 и подстрока в HTML
остались бы верными и на странице, которая исполнилась с ошибкой. Вход — тот
же, что у человека: пароль и код, через админку.

ПРОПУСК — ПРОВАЛ: без playwright проверка ничего не проверяет и выходит ненулём.

    cd storefront && .venv/bin/python test_slots.py
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_DB = os.path.join(tempfile.mkdtemp(prefix="pseudex-slots-db-"), "store.sqlite3")
_STAFF_EMAIL = "slots@pseudex.local"
_STAFF_PASSWORD = "slots-render-password-not-a-secret"
# Ключ TOTP шестнадцатеричным: не секрет — живёт ровно этот прогон, на локальном
# порту, и нужен, чтобы тест посчитал код той же арифметикой, что и сервер.
_STAFF_TOTP_KEY = "3132333435363738393031323334353637383930"

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))
    if not condition:
        FAILURES.append(name)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ── ЗАГЛУШКА ЛИЦЕНЗИОННОГО СЕРВЕРА ────────────────────────────────────────────
#
# Один контейнер держит слот, второй замолчал, третий отпущен. Это и есть
# случай, ради которого всё делалось: занято ОДИН, а строк три.
_STATE = {"reachable": True, "partial": False}


def _instances_body() -> dict:
    now = time.time()
    if _STATE["partial"]:
        # ОТВЕТ БЕЗ ЧИСЕЛ. Сервер ответил, но `occupied`, `live_processes` и
        # бюджет перевыдач не назвал, а у строки не назвал `occupies` и назвал
        # состояние, которого витрина не знает (`cooling` — то самое, что
        # лицензионный сервер отдавал до этой работы). Это не выдумка: так
        # выглядит ответ версии старше витрины, урезанный прокси или сломанный
        # на той стороне, — и подставить здесь ноль значит подписаться числом
        # под тем, чего сервер не говорил.
        return {"org_id": "slotco", "window_seconds": 86400, "alive_seconds": 600,
                "instances": [{"instance_id": "vol-mute", "last_lease": now - 3600,
                               "last_seen": now - 30, "state": "cooling",
                               "free_at": None, "engine_version": "0.3.18"}]}
    return {
        "org_id": "slotco",
        "window_seconds": 86400,
        "alive_seconds": 600,
        "occupied": 1,
        "turnover_last_hour": 2,
        "turnover_budget": 3,
        "instances": [
            {"instance_id": "vol-alive", "last_lease": now - 3600,
             "last_seen": now - 41, "state": "active", "occupies": True,
             "free_at": now - 41 + 600, "live_processes": 4,
             "engine_version": "0.3.18"},
            {"instance_id": "vol-dead", "last_lease": now - 4200,
             "last_seen": now - 1200, "state": "silent", "occupies": False,
             "free_at": None, "live_processes": 0, "engine_version": "0.3.18"},
            {"instance_id": "vol-gone", "last_lease": now - 7200,
             "last_seen": now - 3000, "state": "released", "occupies": False,
             "free_at": None, "live_processes": 0, "engine_version": "0.3.18"},
            # МЕСТО ОТОБРАНО, А ДВИЖОК РАБОТАЕТ. Строку закрыл не клиент, а мы
            # (`released_by='silence'`), чтобы пустить другой контейнер; этот
            # ещё отчитывается и встанет на следующем продлении (Б26ter). В
            # «отпущен» без причины он читался бы как «вы сами остановили».
            {"instance_id": "vol-taken", "last_lease": now - 5400,
             "last_seen": now - 45, "state": "released",
             "released_by": "silence", "occupies": False, "free_at": None,
             "live_processes": 32, "engine_version": "0.3.18"},
            # СЕРВЕР ПРОТИВОРЕЧИТ САМ СЕБЕ: слот отдал, а слышал контейнер
            # минуту назад. Так выглядели 128 живых аренд, показанных
            # свободными; экран обязан назвать это, а не выбрать удобное.
            {"instance_id": "vol-loud", "last_lease": now - 4800,
             "last_seen": now - 60, "state": "silent", "occupies": False,
             "free_at": None, "live_processes": 16, "engine_version": "0.3.18"},
        ],
    }


_USAGE_BODY = {"usage": {"requests": 1200, "values": 800,
                         "capacity_billable": 1200, "capacity_granted": 5000,
                         "capacity_acked": 1000, "capacity_unacked_quanta": 0,
                         "chain_breaks": 0, "unverified_reports": 0,
                         "reports_missing": 0},
               "instances": []}


class _Stub(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802 — имя задано базовым классом
        path = self.path.split("?")[0]
        if not _STATE["reachable"]:
            # НЕ ОТКАЗ С ТЕЛОМ, А ИМЕННО НЕДОСТУПНОСТЬ ЦИФР: коннектор поднимает
            # `LicensingError` на любом не-200, и экран обязан сказать
            # «неизвестно», а не показать ноль.
            self._send(503, {"error": "down"})
            return
        if path == "/admin/instances":
            self._send(200, _instances_body())
        elif path == "/admin/usage":
            self._send(200, _USAGE_BODY)
        elif path == "/admin/fleet":
            body = _instances_body()
            self._send(200, {"orgs": [{"org_id": "slotco",
                                       "usage": _USAGE_BODY["usage"],
                                       "occupied": body["occupied"],
                                       "instances": body["instances"]}],
                             "window_seconds": 86400})
        elif path == "/admin/chains":
            self._send(200, {"history": [], "processes": []})
        elif path == "/admin/plans":
            self._send(200, {"plans": []})
        else:
            self._send(404, {"error": "no such path"})

    def do_POST(self) -> None:  # noqa: N802 — имя задано базовым классом
        # Сид тарифов отправляет `free` на лицензионный сервер и падает
        # командой, если тот отказал: с заданным токеном это настроенное
        # окружение, и «пропустим» здесь было бы неправдой.
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        path = self.path.split("?")[0]
        if path == "/admin/plans":
            self._send(200, {"plan": {"code": "free"}})
        else:
            self._send(404, {"error": "no such path"})

    def log_message(self, fmt: str, *args) -> None:
        return


_SEED = '''
import os
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Membership, Organization
from billing.models import LicenseKey, Plan, Subscription

User = get_user_model()
staff = User.objects.create_user(email=os.environ["STAFF_EMAIL"],
                                 password=os.environ["STAFF_PASSWORD"])
staff.is_staff = staff.is_superuser = True
staff.save()
from django_otp.plugins.otp_totp.models import TOTPDevice
TOTPDevice.objects.create(user=staff, name="slots", confirmed=True,
                          key=os.environ["STAFF_TOTP_KEY"])

# ОДИН ЧЕЛОВЕК НА ОБА ЭКРАНА. Кабинет открывается по членству в организации,
# консоль — по признаку сотрудника и второму фактору; один вход вместо двух
# проверяет ровно то, что проверяется, и не заводит второй способ входа.
org = Organization.objects.create(id="slotco", display_name="ООО Слот",
                                  legal_name="ООО «Слот»", inn="7707083893")
Membership.objects.create(user=staff, organization=org)
plan = Plan.objects.get(code="start")
Subscription.objects.create(organization=org, plan=plan,
                            state=Subscription.ACTIVE,
                            trial_ends_at=timezone.now() - timedelta(days=1),
                            current_period_end=timezone.now() + timedelta(days=30))
LicenseKey.record(org, "ps_live_slotcheck00000000000", "прод", "live")
print(plan.max_instances)
'''


def _start_site(licensing_port: int, site_port: int) -> tuple[subprocess.Popen, int]:
    env = dict(os.environ)
    env.update({
        "DJANGO_SETTINGS_MODULE": "pseudex_site.settings",
        "PSEUDEX_DEBUG": "1",
        "PSEUDEX_SECRET_KEY": "slots-render-test",
        "PSEUDEX_ALLOWED_HOSTS": "127.0.0.1,localhost",
        "PSEUDEX_DB_PATH": _DB,
        "STAFF_EMAIL": _STAFF_EMAIL,
        "STAFF_PASSWORD": _STAFF_PASSWORD,
        "STAFF_TOTP_KEY": _STAFF_TOTP_KEY,
        "PSEUDEX_LICENSING_ADMIN_URL": f"http://127.0.0.1:{licensing_port}",
        "PSEUDEX_LICENSE_STOREFRONT_TOKEN": "slots-stub-token",
    })
    for command in (["migrate", "--noinput", "-v", "0"], ["seed_plans", "-v", "0"]):
        subprocess.run([sys.executable, "manage.py", *command], cwd=str(_ROOT),
                       env=env, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    seeded = subprocess.run([sys.executable, "manage.py", "shell", "-c", _SEED],
                            cwd=str(_ROOT), env=env, check=True,
                            capture_output=True, text=True)
    allowed = int(seeded.stdout.strip().splitlines()[-1])
    server = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{site_port}",
         "--noreload", "--insecure"],
        cwd=str(_ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{site_port}/", timeout=2)
            return server, allowed
        except urllib.error.HTTPError:
            return server, allowed
        except OSError:
            time.sleep(0.5)
    server.terminate()
    raise RuntimeError("витрина не поднялась")


def _launch(pw):
    """Штатный chromium, а если номер сборки не тот — лежащий рядом."""
    try:
        return pw.chromium.launch()
    except Exception as error:  # noqa: BLE001 — любая причина значит «не тот»
        root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
        found = sorted(Path(root).glob("chromium-*/chrome-linux/chrome")) if root else []
        if not found:
            raise RuntimeError(
                f"chromium не запускается ({error}); поставьте его "
                f"`python -m playwright install chromium`") from error
        return pw.chromium.launch(executable_path=str(found[-1]))


def _unit_checks() -> None:
    """Пересчёт занятости — НЕ в витрине, а число, которого сервер не назвал, —
    НЕ ноль.

    Второе — вся цена этого захода: вердикт видел «контейнеры — 0 из 1 занято»
    при 128 живых арендах и «процессов 0» у контейнера с тридцатью двумя
    воркерами. Оба нуля пришли не с сервера, а из `get(key, 0)` витрины.
    """
    sys.path.insert(0, str(_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    from billing import slots

    now = time.time()
    view = slots.describe(_instances_body(), now)
    rows = {row["instance_id"]: row for row in view["rows"]}
    check("занято берётся у сервера, а не из длины списка",
          view["occupied"] == 1 and len(view["rows"]) == 5,
          f"occupied={view['occupied']} строк={len(view['rows'])}")
    states = [row["state"] for row in view["rows"]]
    check("состояния доезжают как есть, а отобранное место названо отобранным",
          states == ["active", "silent", "released", "reclaimed", "silent"],
          str(states))
    holds = [row["holds"] for row in view["rows"]]
    check("слот держит только живой",
          holds == [True, False, False, False, False], str(holds))
    check("срок до самостоятельного освобождения назван только там, где сервер его назвал",
          bool(rows["vol-alive"]["frees_in"]) and not rows["vol-dead"]["frees_in"],
          f"живой={rows['vol-alive']['frees_in']!r} молчащий={rows['vol-dead']['frees_in']!r}")
    check("срок молчания берётся из alive_seconds сервера, а не из константы",
          view["alive_label"] == "10 мин", view["alive_label"])
    check("рабочие процессы доезжают числом — это то, чем считается отказ по потолку",
          rows["vol-taken"]["live_processes"] == 32
          and rows["vol-alive"]["live_processes"] == 4,
          f"отобранный={rows['vol-taken']['live_processes']} "
          f"живой={rows['vol-alive']['live_processes']}")
    check("плашка собрана по occupies, а не по имени состояния",
          rows["vol-alive"]["pill"] == "ДЕРЖИТ СЛОТ"
          and rows["vol-taken"]["pill"] == "МЕСТО ОТОБРАНО — СЛОТ СВОБОДЕН",
          f"{rows['vol-alive']['pill']!r} / {rows['vol-taken']['pill']!r}")
    check("контейнер, которого сервер слышал только что, отмечен, хотя слот отдан",
          rows["vol-loud"]["heard_recently"] is True
          and rows["vol-dead"]["heard_recently"] is False,
          f"слышали 60 с назад={rows['vol-loud']['heard_recently']} "
          f"молчит 20 мин={rows['vol-dead']['heard_recently']}")

    # ── ОТВЕТ БЕЗ ЧИСЕЛ. Поле, которого нет, — это «сервер не назвал».
    _STATE["partial"] = True
    thin = slots.describe(_instances_body(), now)
    _STATE["partial"] = False
    mute = thin["rows"][0]
    check("занятость, которой сервер не назвал, — не ноль",
          thin["occupied"] is None, repr(thin["occupied"]))
    check("бюджет перевыдач, которого сервер не назвал, — не ноль",
          thin["turnover_last_hour"] is None and thin["turnover_budget"] is None,
          f"{thin['turnover_last_hour']!r} из {thin['turnover_budget']!r}")
    check("процессы, которых сервер не назвал, — не ноль",
          mute["live_processes"] is None, repr(mute["live_processes"]))
    check("занятость строки, которой сервер не назвал, не читается как «свободно»",
          mute["holds"] is None and "ЗАНЯТОСТЬ НЕИЗВЕСТНА" in mute["pill"],
          f"holds={mute['holds']!r} плашка={mute['pill']!r}")
    check("незнакомое состояние НАЗВАНО, а не подведено под знакомое",
          "cooling" in mute["pill"] and "СЛОТ СВОБОДЕН" not in mute["pill"],
          mute["pill"])

    silent = slots.unknown()
    check("молчание сервера — это «неизвестно», а не ноль",
          silent["known"] is False and silent["occupied"] is None
          and silent["rows"] == [],
          f"known={silent['known']} occupied={silent['occupied']!r}")


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright не установлен, а без него эта проверка ничего не "
              "проверяет:\n  pip install playwright && "
              "python -m playwright install chromium")
        return 1

    _unit_checks()

    licensing_port, site_port = _free_port(), _free_port()
    stub = HTTPServer(("127.0.0.1", licensing_port), _Stub)
    threading.Thread(target=stub.serve_forever, daemon=True).start()

    server, allowed = _start_site(licensing_port, site_port)
    base = f"http://127.0.0.1:{site_port}"
    admin_path = os.environ.get("PSEUDEX_ADMIN_PATH", "admin")
    try:
        with sync_playwright() as pw:
            browser = _launch(pw)
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

            # --- вход паролем и кодом, как у человека --------------------
            from django_otp.oath import totp as _totp
            page.goto(f"{base}/{admin_path}/login/?next=/app/", wait_until="networkidle")
            page.fill("input[name=username]", _STAFF_EMAIL)
            page.fill("input[name=password]", _STAFF_PASSWORD)
            page.click("input[type=submit], button[type=submit]")
            page.wait_for_load_state("networkidle")
            page.select_option("select[name=otp_device]", index=0)
            page.fill("input[name=otp_token]",
                      "%06d" % _totp(bytes.fromhex(_STAFF_TOTP_KEY)))
            page.click("input[type=submit], button[type=submit]")
            page.wait_for_load_state("networkidle")
            check("вошёл паролем и кодом", "/login" not in page.url,
                  page.url.replace(base, ""))

            # --- КАБИНЕТ ------------------------------------------------
            page.goto(f"{base}/app/", wait_until="networkidle")
            body = page.inner_text("body")
            check("кабинет отрисован",
                  len(body) > 200 and "Traceback" not in body,
                  f"{len(body)} симв." + (f", ошибки: {errors[:2]}" if errors else ""))
            check("кабинет считает ЗАНЯТЫЕ слоты, а не строки списка",
                  f"1 из {allowed} занято" in body
                  and f"3 из {allowed} занято" not in body,
                  f"в тексте: {'есть 1 из' if f'1 из {allowed}' in body else 'НЕТ'}; "
                  f"{'ЕСТЬ 3 из' if f'3 из {allowed}' in body else 'нет 3 из'}")
            check("замолчавший контейнер назван молчащим, а слот его — свободным",
                  "vol-dead" in body and "МОЛЧИТ — СЛОТ СВОБОДЕН" in body,
                  "строка есть" if "vol-dead" in body else "строки нет")
            check("остановленный контейнер не показан работающим",
                  "vol-gone" in body and "ОСТАНОВЛЕН — СЛОТ СВОБОДЕН" in body)
            check("живой контейнер назван живым и со сроком",
                  "vol-alive" in body and "ДЕРЖИТ СЛОТ" in body
                  and "если замолчит" in body)
            check("отобранное место названо отобранным, а не «вы сами остановили»",
                  "vol-taken" in body and "МЕСТО ОТОБРАНО — СЛОТ СВОБОДЕН" in body,
                  "строка есть" if "vol-taken" in body else "строки нет")
            check("кабинет говорит, что будет с работающим контейнером, у которого забрали место",
                  "на следующем продлении аренды он получит отказ" in body
                  and "НА ТОМ ЖЕ ТОМЕ" in body)
            check("контейнер, которого сервер слышал только что, не выдан за просто свободный",
                  "vol-loud" in body
                  and "слот у него заберут при следующем продлении" in body)
            # ТЕ САМЫЕ 32, ПО КОТОРЫМ ОТКАЗЫВАЕТ ПОТОЛОК. Клиент читает
            # «это 32 рабочих процесса, сейчас живых 32» и до сих пор не мог
            # увидеть эту величину ни на одном своём экране.
            check("кабинет показывает живые процессы каждого контейнера",
                  "рабочих процессов 32" in body and "рабочих процессов 4" in body)
            check("кабинет говорит, через сколько молчания слот освободится сам",
                  "10 мин молчания" in body, "срок из alive_seconds сервера")
            check("кабинет говорит, что переразвёртывание на том же томе слот не теряет",
                  "НА ТОМ ЖЕ ТОМЕ" in body and "pseudex-data:/data" in body)
            check("кабинет называет израсходованный бюджет перевыдач",
                  "2 раза из 3" in body, "перевыдач за час")
            # ВЕТКА, КОТОРОЙ БОЛЬШЕ НЕТ, ПРОВЕРЯЕТСЯ ПО ИСХОДНИКУ, А НЕ ПО
            # ЭКРАНУ: сервер больше не отдаёт `cooling`, поэтому ветка по нему
            # на экране просто не сработает — и проверка, которая смотрит на
            # отрисованное, пройдёт и на старом шаблоне. Утверждение здесь
            # именно про шаблон: ветки по остыванию в витрине не осталось.
            cooling = [str(path.relative_to(_ROOT))
                       for path in (_ROOT / "templates").rglob("*.html")
                       if "cooling" in path.read_text()]
            check("ни один шаблон витрины не ветвится по «остывает»",
                  not cooling, f"осталось в {cooling or 'нигде'}")

            # --- КОНСОЛЬ: карточка клиента ------------------------------
            page.goto(f"{base}/{admin_path}/ops/slotco/", wait_until="networkidle")
            console = page.inner_text("body")
            check("карточка клиента отрисована",
                  len(console) > 200 and "Traceback" not in console,
                  f"{len(console)} симв.")
            check("консоль показывает занято числом сервера",
                  "занято сейчас" in console and console.count("ДЕРЖИТ СЛОТ") == 1,
                  f"«ДЕРЖИТ СЛОТ» встречается {console.count('ДЕРЖИТ СЛОТ')} раз(а)")
            check("консоль различает состояния и называет отобранное место",
                  "МОЛЧИТ — СЛОТ СВОБОДЕН" in console
                  and "ОСТАНОВЛЕН — СЛОТ СВОБОДЕН" in console
                  and "МЕСТО ОТОБРАНО — СЛОТ СВОБОДЕН" in console)
            check("консоль называет срок молчания и бюджет перевыдач",
                  "10 мин молчания" in console and "2 из 3" in console)
            # СТРОКА ЖИВОГО ИНСТАНСА ЦЕЛИКОМ: «столбец есть» на этой странице
            # проходило бы и на старом шаблоне (слово встречается в соседней
            # таблице), а утверждается здесь именно то, что в строке инстанса
            # стоят его живые процессы и версия его движка.
            alive_row = page.locator("tr", has_text="vol-alive").first.inner_text()
            check("в строке живого инстанса стоят его процессы и версия движка",
                  "4" in alive_row and "0.3.18" in alive_row,
                  alive_row.replace("\n", " | "))

            taken_row = page.locator("tr", has_text="vol-taken").first.inner_text()
            check("в строке отобранного места стоят его живые процессы и что будет дальше",
                  "32" in taken_row and "409" in taken_row,
                  taken_row.replace("\n", " | "))

            # --- КОНСОЛЬ: флот ------------------------------------------
            page.goto(f"{base}/{admin_path}/ops/", wait_until="networkidle")
            fleet = page.inner_text("body")
            check("флот показывает занятые слоты, а не длину списка аренд",
                  f"1 / {allowed}" in fleet and f"3 / {allowed}" not in fleet,
                  f"{'есть 1 /' if f'1 / {allowed}' in fleet else 'НЕТ 1 /'}; "
                  f"{'ЕСТЬ 3 /' if f'3 / {allowed}' in fleet else 'нет 3 /'}")

            # --- СЕРВЕР ОТВЕТИЛ, НО ЧИСЕЛ НЕ НАЗВАЛ ---------------------
            #
            # Именно так экраны и соврали: ноль пришёл не с сервера, а из
            # `get(key, 0)` витрины, и «0 из 1 занято» стояло при 128 живых
            # арендах. Ответ без полей — это вопрос без ответа, а не ноль.
            _STATE["partial"] = True
            page.goto(f"{base}/app/", wait_until="networkidle")
            thin = page.inner_text("body")
            check("кабинет не подставляет ноль за не названную сервером занятость",
                  "не назвал занятость" in thin
                  and f"0 из {allowed} занято" not in thin,
                  f"{'сказано' if 'не назвал занятость' in thin else 'НЕ СКАЗАНО'}; "
                  f"{'ЕСТЬ ноль' if f'0 из {allowed} занято' in thin else 'нуля нет'}")
            check("незнакомое состояние названо, а не покрашено в знакомое",
                  "ЗАНЯТОСТЬ НЕИЗВЕСТНА" in thin and "cooling" in thin
                  and "СЛОТ СВОБОДЕН" not in thin,
                  "есть «свободен» на неизвестной занятости"
                  if "СЛОТ СВОБОДЕН" in thin else "свободным не назван")
            check("кабинет не подставляет ноль за не названные процессы",
                  "рабочих процессов сервер не назвал" in thin
                  and "рабочих процессов 0" not in thin)
            page.goto(f"{base}/{admin_path}/ops/slotco/", wait_until="networkidle")
            thin_console = page.inner_text("body")
            mute_row = page.locator("tr", has_text="vol-mute").first
            # КЛЕТКА, А НЕ СТРОКА: «нуля в строке нет» прошло бы и на нуле —
            # в той же строке стоит версия 0.3.18.
            mute_processes = mute_row.locator("td").nth(2).inner_text().strip()
            check("консоль пишет «не назвал» вместо нуля занятых",
                  "не назвал занятость" in thin_console
                  and "занято по тарифу 0" not in thin_console)
            check("в строке без чисел стоит прочерк, а не ноль процессов",
                  mute_processes == "—"
                  and "ЗАНЯТОСТЬ НЕИЗВЕСТНА" in mute_row.inner_text(),
                  f"клетка процессов: {mute_processes!r}")
            _STATE["partial"] = False

            # --- МОЛЧАНИЕ СЕРВЕРА — ЭТО «НЕИЗВЕСТНО» --------------------
            _STATE["reachable"] = False
            page.goto(f"{base}/app/", wait_until="networkidle")
            offline = page.inner_text("body")
            check("кабинет открывается, когда лицензионный сервер молчит",
                  len(offline) > 200 and "Traceback" not in offline,
                  f"{len(offline)} симв.")
            check("молчание сервера показано молчанием, а не нулём занятых слотов",
                  "неизвестно" in offline and f"0 из {allowed} занято" not in offline,
                  f"{'сказано' if 'неизвестно' in offline else 'НЕ СКАЗАНО'}; "
                  f"{'ЕСТЬ ноль' if f'0 из {allowed} занято' in offline else 'нуля нет'}")
            page.goto(f"{base}/{admin_path}/ops/", wait_until="networkidle")
            offline_fleet = page.inner_text("body")
            check("флот на молчащем сервере пишет «?», а не ноль занятых",
                  f"? / {allowed}" in offline_fleet
                  and f"0 / {allowed}" not in offline_fleet,
                  f"{'есть ?' if f'? / {allowed}' in offline_fleet else 'НЕТ ?'}; "
                  f"{'ЕСТЬ ноль' if f'0 / {allowed}' in offline_fleet else 'нуля нет'}")
            _STATE["reachable"] = True
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
        stub.shutdown()

    print("\n" + ("ВСЁ ЗЕЛЁНОЕ" if not FAILURES else f"УПАЛО: {FAILURES}"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
