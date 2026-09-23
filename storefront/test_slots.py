"""ЭКРАН, КОТОРЫЙ ВРЁТ ПРО СЛОТ, — ЭТО ТОТ ЖЕ ДЕФЕКТ, ЧТО И СЛОТ, КОТОРЫЙ ДЕРЖИТ ТРУП.

Что здесь доказывается (Б26, Б26bis, Б26ter, Б26quater;
`research/2026-09-22-instance-liveness-and-slots.md`):

  * «занято» — это ЧИСЛО С СЕРВЕРА, а не длина списка. В ответе
    `/admin/instances` есть и `silent`, и `released` — контейнеры, которые слот
    НЕ держат; кабинет показывал бы «4 из 1 занято» человеку, у которого занят
    один, а консоль — превышение тарифа, которого нет;
  * КАЖДОЕ состояние клиента различимо на вид и названо своим именем: держит,
    молчит, остановлен сам, МЕСТО ОТОБРАНО, упёрся в потолок рабочих процессов;
  * отобранное место названо отобранным. Клиент, у которого мы забрали слот,
    обязан прочитать, что это сделали МЫ и почему (он молчал дольше срока), —
    а не «вы сами остановили контейнер»;
  * молчание лицензионного сервера показано молчанием, а не нулём: «0 из 1
    занято» читается как ответ, и человек делает из него вывод, что
    контейнеров у него нет.

ПОЧЕМУ ЭТА ПРОВЕРКА ПЕРЕПИСАНА ЦЕЛИКОМ (Б26quater, последний абзац).

Предыдущая ездила на теле, написанном рукой: в нём стояло `released_by:
"silence"` и `live_processes: 32` у отобранного места — поле, которого сервер
тогда не отдавал вовсе, и число, которого он в этом состоянии не даёт.
Проверка, собранная из полей, которых сервер никогда не присылает, провалиться
не может: она охраняет фантазию автора, а не экран. Теперь ответы СНИМАЮТСЯ с
настоящего `licensing.devserver` (`test_slots_stand.py`): организацию доводят
до каждого состояния настоящими вызовами `/v1/lease`, `/v1/usage`,
`/v1/release`, место у молчащего отбирают по-настоящему, в потолок рабочих
процессов упираются по-настоящему — и экраны рисуются по снятым телам.

ЧТО ОСТАЛОСЬ ЗАГЛУШКОЙ И ПОЧЕМУ. Тела отдаёт локальный HTTP-стенд, а не сам
лицензионный сервер: занятость зависит от времени (при `ALIVE_SECONDS=3` живой
контейнер замолкает раньше, чем браузер откроет вторую страницу), поэтому пять
состояний удерживаются в кадре только снимком. Заглушка ничего не вычисляет:
она отдаёт снятые байты по тому же пути и через тот же коннектор
(`billing/licensing.py`), то есть цепочка «ответ ручки → коннектор → вьюха →
шаблон» проверяется целиком. Два вырожденных случая — сервер не ответил и
сервер ответил без чисел — получены ВЫЧИТАНИЕМ полей из настоящего тела: так
выглядит ответ версии старше витрины или урезанный прокси, и подставить здесь
ноль значило бы подписаться числом под тем, чего сервер не говорил.

НАСТОЯЩИЙ БРАУЗЕР, как у остальных отрисовочных проверок витрины
(`test_ops_renders.py`, `test_configurator_renders.py`): 200 и подстрока в HTML
остались бы верными и на странице, которая исполнилась с ошибкой. Вход — тот
же, что у человека: пароль и код, через админку.

ПРОПУСК — ПРОВАЛ: без playwright и без окружения движка проверка ничего не
проверяет и выходит ненулём.

    cd storefront && .venv/bin/python test_slots.py
"""

import copy
import json
import os
import re
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
_ENGINE = _ROOT.parent / "prototype"
_WORK = Path(tempfile.mkdtemp(prefix="pseudex-slots-"))
_DB = str(_WORK / "store.sqlite3")
_CAPTURE_PATH = _WORK / "captured.json"
# Две организации и два человека: тарифный потолок процессов считается по ВСЕЙ
# организации, поэтому молчащий ключ соседнего контейнера занял бы место в тех
# же тридцати двух и отказ пришёл бы по другой причине. Кабинет показывает
# организацию по старшему членству, значит у второй организации свой вход.
_SLOT_ORG, _CEIL_ORG = "slotco", "ceilco"
_STAFF = {_SLOT_ORG: "slots@pseudex.local", _CEIL_ORG: "ceiling@pseudex.local"}
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


# ── СНЯТЫЕ ОТВЕТЫ НАСТОЯЩЕГО ЛИЦЕНЗИОННОГО СЕРВЕРА ───────────────────────────


def _engine_python() -> str:
    """Интерпретатор ДВИЖКА: ключ процесса — это X25519-личность `pyrage`,
    которой в окружении витрины нет и быть не должно (витрина не зависит от
    движка). Не найден — это провал, а не пропуск: без него проверка
    проверяет заглушку."""
    named = os.environ.get("PSEUDEX_ENGINE_PYTHON", "")
    if named and Path(named).exists():
        return named
    default = _ENGINE / ".venv" / "bin" / "python"
    if default.exists():
        return str(default)
    raise RuntimeError(
        "не найден интерпретатор движка: поставьте prototype/.venv или "
        "укажите PSEUDEX_ENGINE_PYTHON — без него ответы сервера снять нечем")


def _capture() -> dict:
    """Поднять настоящий лицензионный сервер и снять с него ответы."""
    started = time.time()
    result = subprocess.run(
        [_engine_python(), str(_ROOT / "test_slots_stand.py"),
         "--out", str(_CAPTURE_PATH)],
        cwd=str(_ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("стенд лицензионного сервера не отработал:\n"
                           + result.stdout[-2000:] + result.stderr[-4000:])
    print(f"стенд отработал за {time.time() - started:.0f} с: {_CAPTURE_PATH}")
    return json.loads(_CAPTURE_PATH.read_text())


CAPTURE: dict = {}
# Какое из снятых тел отдавать по `slotco`: снимок с пятью состояниями,
# он же после того, как отобранный контейнер снова отчитался, урезанный и
# недоступность.
_MODE = {"instances": "snapshot"}


def _thin(body: dict) -> dict:
    """ОТВЕТ БЕЗ ЧИСЕЛ — ВЫЧИТАНИЕМ ИЗ НАСТОЯЩЕГО, а не выдумкой.

    Сервер ответил, но `occupied`, `live_processes`, `held_places` и бюджет
    перевыдач не назвал, а у строки не назвал `occupies` и назвал состояние,
    которого витрина не знает. Так выглядит ответ версии старше витрины,
    урезанный прокси или сломанный на той стороне. `cooling` — не выдумка: это
    то самое состояние, которое лицензионный сервер отдавал до этой работы, и
    экран обязан НАЗВАТЬ его, а не подвести под знакомое.
    """
    thin = copy.deepcopy(body)
    for field in ("occupied", "turnover_last_hour", "turnover_budget"):
        thin.pop(field, None)
    rows = thin.get("instances", [])[:1]
    for row in rows:
        for field in ("occupies", "live_processes", "held_places", "free_at"):
            row.pop(field, None)
        row["state"] = "cooling"
    thin["instances"] = rows
    return thin


def _shift(body: dict, captured_at: float) -> dict:
    """Снимок, приведённый к «сейчас»: ОДИН сдвиг на все отметки времени.

    Тело снято раньше, чем браузер его рисует, а занятость — величина
    относительно текущего момента. Без сдвига экран говорил бы «на связи 2 мин
    назад» про контейнер, который сервер в этом же теле назвал живым при сроке
    молчания в три секунды, — и проверка ловила бы этот разрыв вместо дефекта.
    Сдвиг общий для всех отметок, поэтому все отношения между ними — кто
    старше, кто свежее срока — сохраняются в точности.
    """
    delta = time.time() - captured_at
    shifted = copy.deepcopy(body)
    for row in shifted.get("instances", []):
        for field in ("last_lease", "last_seen", "free_at"):
            if isinstance(row.get(field), (int, float)):
                row[field] = row[field] + delta
    return shifted


class _Stub(BaseHTTPRequestHandler):
    """Отдаёт СНЯТЫЕ байты по тем же путям, что и лицензионный сервер."""

    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _instances(self, org_id: str) -> tuple[int, dict]:
        mode = _MODE["instances"]
        if mode == "down":
            # НЕ ОТКАЗ С ТЕЛОМ, А ИМЕННО НЕДОСТУПНОСТЬ ЦИФР: коннектор поднимает
            # `LicensingError` на любом не-200, и экран обязан сказать
            # «неизвестно», а не показать ноль.
            return 503, {"error": "down"}
        if org_id == _CEIL_ORG:
            captured = CAPTURE["ceiling"]
            return 200, _shift(captured["instances"], captured["instances_at"])
        captured = CAPTURE["slots"]
        if mode == "echo":
            return 200, _shift(captured["instances_after_echo"],
                               captured["instances_after_echo_at"])
        body = _shift(captured["instances"], captured["instances_at"])
        return 200, _thin(body) if mode == "thin" else body

    def do_GET(self) -> None:  # noqa: N802 — имя задано базовым классом
        path, _, query = self.path.partition("?")
        org_id = ""
        for pair in query.split("&"):
            if pair.startswith("org_id="):
                org_id = pair.split("=", 1)[1]
        if _MODE["instances"] == "down" and path != "/admin/plans":
            self._send(503, {"error": "down"})
            return
        captured = CAPTURE["ceiling"] if org_id == _CEIL_ORG else CAPTURE["slots"]
        if path == "/admin/instances":
            self._send(*self._instances(org_id))
        elif path == "/admin/usage":
            self._send(200, captured["usage"])
        elif path == "/admin/fleet":
            self._send(200, CAPTURE["fleet"])
        elif path == "/admin/chains":
            self._send(200, captured["chains"])
        elif path == "/admin/plans":
            self._send(200, CAPTURE["plans"])
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


# ── ВИТРИНА ──────────────────────────────────────────────────────────────────

_SEED = '''
import os
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Membership, Organization
from billing.models import LicenseKey, Plan, Subscription
from django_otp.plugins.otp_totp.models import TOTPDevice

User = get_user_model()
plan = Plan.objects.get(code=os.environ["PLAN_CODE"])

# ОДИН ЧЕЛОВЕК НА ОБА ЭКРАНА СВОЕЙ ОРГАНИЗАЦИИ. Кабинет открывается по членству,
# консоль — по признаку сотрудника и второму фактору; один вход вместо двух
# проверяет ровно то, что проверяется, и не заводит второй способ входа.
for org_id, display, email in ((os.environ["SLOT_ORG"], "ООО Слот", os.environ["SLOT_EMAIL"]),
                              (os.environ["CEIL_ORG"], "ООО Потолок", os.environ["CEIL_EMAIL"])):
    staff = User.objects.create_user(email=email, password=os.environ["STAFF_PASSWORD"])
    staff.is_staff = staff.is_superuser = True
    staff.save()
    TOTPDevice.objects.create(user=staff, name="slots", confirmed=True,
                              key=os.environ["STAFF_TOTP_KEY"])
    org = Organization.objects.create(id=org_id, display_name=display,
                                      legal_name=display, inn="7707083893")
    Membership.objects.create(user=staff, organization=org)
    Subscription.objects.create(organization=org, plan=plan,
                                state=Subscription.ACTIVE,
                                trial_ends_at=timezone.now() - timedelta(days=1),
                                current_period_end=timezone.now() + timedelta(days=30))
    LicenseKey.record(org, "ps_live_" + org_id + "0000000000", "прод", "live")
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
        "SLOT_ORG": _SLOT_ORG,
        "CEIL_ORG": _CEIL_ORG,
        "SLOT_EMAIL": _STAFF[_SLOT_ORG],
        "CEIL_EMAIL": _STAFF[_CEIL_ORG],
        # ТОТ ЖЕ ТАРИФ, ЧТО У ЛИЦЕНЗИОННОГО СЕРВЕРА: «занято 1 из 1» — это его
        # число рядом с нашим, и разные тарифы по две стороны экрана читались бы
        # как ошибка счёта.
        "PLAN_CODE": CAPTURE["slots"]["plan"],
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


def _sign_in(page, base: str, admin_path: str, email: str) -> None:
    """Вход паролем и кодом — РОВНО ОДИН РАЗ НА ЧЕЛОВЕКА ЗА ПРОГОН.

    Второй вход тем же человеком в том же тридцатисекундном шаге django-otp
    отвергает как повтор кода («Invalid token»), и проверка падала не там, где
    дефект. Поэтому экраны каждой организации сгруппированы: первый человек
    проходит все свои случаи, включая вырожденные, и только потом входит второй.
    """
    from django_otp.oath import totp as _totp
    # ВЫХОД — СБРОСОМ COOKIE, А НЕ `/admin/logout/`: в Django 5 выход только
    # POST-ом, GET отвечает 405, сессия остаётся, и форма входа не появляется —
    # второй человек молча оказался бы первым.
    page.context.clear_cookies()
    page.goto(f"{base}/{admin_path}/login/?next=/app/", wait_until="networkidle")
    page.fill("input[name=username]", email)
    page.fill("input[name=password]", _STAFF_PASSWORD)
    page.click("input[type=submit], button[type=submit]")
    page.wait_for_load_state("networkidle")
    page.select_option("select[name=otp_device]", index=0)
    page.fill("input[name=otp_token]", "%06d" % _totp(bytes.fromhex(_STAFF_TOTP_KEY)))
    page.click("input[type=submit], button[type=submit]")
    page.wait_for_load_state("networkidle")


# ── ЧТО ГОВОРИТ СНЯТОЕ ТЕЛО ДО ВСЯКОЙ ОТРИСОВКИ ──────────────────────────────


def _payload_checks() -> None:
    """Сначала — что в теле СЕРВЕРА есть ровно то, на чём стоит экран.

    Эта проверка и есть ответ на Б26quater: раньше здесь стояло тело, написанное
    рукой, и `released_by` в нём был выдумкой автора. Если сервер перестанет
    называть причину освобождения, падать обязано ЗДЕСЬ — с именем поля, — а не
    в виде зелёной страницы, на которой отобранное место названо остановленным.
    """
    slots = CAPTURE["slots"]
    rows = {row["instance_id"]: row for row in slots["instances"]["instances"]}
    check("снятое тело описывает все четыре состояния контейнера",
          set(rows) == {slots["holding"], slots["silent"], slots["released"],
                        slots["reclaimed"]}, ", ".join(sorted(rows)))
    check("сервер НАЗЫВАЕТ причину освобождения, а не оставляет её экрану",
          rows[slots["reclaimed"]].get("released_by") == "silence"
          and rows[slots["released"]].get("released_by") == "process",
          f"отобранный={rows[slots['reclaimed']].get('released_by')!r} "
          f"остановленный={rows[slots['released']].get('released_by')!r}")
    check("отобранное место и остановленный контейнер отличаются ТОЛЬКО причиной",
          rows[slots["reclaimed"]]["state"] == rows[slots["released"]]["state"]
          == "released",
          "иначе состояние различает их само — тогда причина не нужна")
    ceiling = CAPTURE["ceiling"]
    refusal = ceiling["refusals"]["process_ceiling"]["detail"]
    live = [int(number) for number in re.findall(r"\d+", refusal)]
    row = ceiling["instances"]["instances"][0]
    check("отказ по потолку процессов — настоящий и называет число живых процессов",
          ceiling["refusals"]["process_ceiling"]["status"] == 409
          and row["live_processes"] in live,
          f"живых по строке {row['live_processes']}, числа отказа {live}")
    check("сервер называет и занятые места под потолком тарифа",
          isinstance(row.get("held_places"), int),
          f"held_places={row.get('held_places')!r}")


def _unit_checks() -> None:
    """Пересчёт занятости — НЕ в витрине, а число, которого сервер не назвал, —
    НЕ ноль.

    Второе — цена третьего захода: вердикт видел «контейнеры — 0 из 1 занято»
    при 128 живых арендах и «процессов 0» у контейнера с тридцатью двумя
    воркерами. Оба нуля пришли не с сервера, а из `get(key, 0)` витрины.
    """
    sys.path.insert(0, str(_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pseudex_site.settings")
    from billing import slots as slotview

    captured = CAPTURE["slots"]
    body = captured["instances"]
    # «СЕЙЧАС» — ЭТО МОМЕНТ СЪЁМКИ. Тело абсолютное, занятость относительная;
    # считать его по часам этого прогона значило бы состарить снимок на время
    # работы стенда и мерить не то.
    now = captured["instances_at"]
    view = slotview.describe(body, now)
    rows = {row["instance_id"]: row for row in view["rows"]}
    check("занято берётся у сервера, а не из длины списка",
          view["occupied"] == body["occupied"] == 1 and len(view["rows"]) == 4,
          f"occupied={view['occupied']} строк={len(view['rows'])}")
    check("состояния доезжают как есть, а отобранное место названо отобранным",
          rows[captured["holding"]]["state"] == "active"
          and rows[captured["silent"]]["state"] == "silent"
          and rows[captured["released"]]["state"] == "released"
          and rows[captured["reclaimed"]]["state"] == "reclaimed",
          str({name: row["state"] for name, row in rows.items()}))
    check("слот держит только живой",
          [row["holds"] for row in view["rows"]] == [True, False, False, False],
          str([row["holds"] for row in view["rows"]]))
    check("срок до самостоятельного освобождения назван только там, где сервер его назвал",
          bool(rows[captured["holding"]]["frees_in"])
          and not rows[captured["silent"]]["frees_in"],
          f"живой={rows[captured['holding']]['frees_in']!r} "
          f"молчащий={rows[captured['silent']]['frees_in']!r}")
    check("срок молчания берётся из alive_seconds сервера, а не из константы",
          view["alive_label"] == slotview.ago(body["alive_seconds"])
          and view["alive_label"] != slotview.ago(600),
          f"{view['alive_label']!r} при alive_seconds={body['alive_seconds']}")
    check("рабочие процессы доезжают числом — это то, чем считается отказ по потолку",
          rows[captured["holding"]]["live_processes"] == captured["workers"]["alive"],
          f"живой={rows[captured['holding']]['live_processes']} "
          f"воркеров подняли {captured['workers']['alive']}")
    check("плашка собрана по occupies, а не по имени состояния",
          rows[captured["holding"]]["pill"] == "ДЕРЖИТ СЛОТ"
          and rows[captured["reclaimed"]]["pill"] == "МЕСТО ОТОБРАНО — СЛОТ СВОБОДЕН",
          f"{rows[captured['holding']]['pill']!r} / "
          f"{rows[captured['reclaimed']]['pill']!r}")

    echoed = slotview.describe(captured["instances_after_echo"],
                               captured["instances_after_echo_at"])
    echo_row = {row["instance_id"]: row for row in echoed["rows"]}[captured["reclaimed"]]
    check("отобранный контейнер, который снова отчитался, отмечен как ещё работающий",
          echo_row["heard_recently"] is True
          and rows[captured["reclaimed"]]["heard_recently"] is False,
          f"после отчёта={echo_row['heard_recently']} "
          f"до него={rows[captured['reclaimed']]['heard_recently']}")

    ceiling = slotview.describe(CAPTURE["ceiling"]["instances"],
                                CAPTURE["ceiling"]["instances_at"])
    row = CAPTURE["ceiling"]["instances"]["instances"][0]
    check("места под потолком тарифа складываются по строкам сервера",
          ceiling.get("held_places") == row["held_places"]
          and ceiling.get("live_processes") == row["live_processes"],
          f"мест={ceiling.get('held_places', 'нет поля')} "
          f"живых={ceiling.get('live_processes', 'нет поля')} "
          f"при {row['held_places']}/{row['live_processes']} в строке сервера")

    # ── ОТВЕТ БЕЗ ЧИСЕЛ. Поле, которого нет, — это «сервер не назвал».
    thin = slotview.describe(_thin(body), now)
    mute = thin["rows"][0]
    check("занятость, которой сервер не назвал, — не ноль",
          thin["occupied"] is None, repr(thin["occupied"]))
    check("бюджет перевыдач, которого сервер не назвал, — не ноль",
          thin["turnover_last_hour"] is None and thin["turnover_budget"] is None,
          f"{thin['turnover_last_hour']!r} из {thin['turnover_budget']!r}")
    # ЧЕРЕЗ `.get`, А НЕ ПО КЛЮЧУ: витрина, которая поле ПОТЕРЯЛА, обязана
    # дать здесь красную строку с именем поля, а не KeyError посреди прогона.
    check("процессы и места, которых сервер не назвал, — не ноль",
          mute.get("live_processes", 0) is None and mute.get("held_places", 0) is None
          and thin.get("live_processes", 0) is None
          and thin.get("held_places", 0) is None,
          f"строка={mute.get('live_processes', 'нет поля')!r}/"
          f"{mute.get('held_places', 'нет поля')!r} "
          f"итог={thin.get('live_processes', 'нет поля')!r}/"
          f"{thin.get('held_places', 'нет поля')!r}")
    check("занятость строки, которой сервер не назвал, не читается как «свободно»",
          mute["holds"] is None and "ЗАНЯТОСТЬ НЕИЗВЕСТНА" in mute["pill"],
          f"holds={mute['holds']!r} плашка={mute['pill']!r}")
    check("незнакомое состояние НАЗВАНО, а не подведено под знакомое",
          "cooling" in mute["pill"] and "СЛОТ СВОБОДЕН" not in mute["pill"],
          mute["pill"])

    # ПРИЧИНА ОСВОБОЖДЕНИЯ, КОТОРОЙ ВИТРИНА НЕ ЗНАЕТ. Значение из словаря самого
    # сервера (`store.py::active_instances`: process | silence | admin), но
    # `/admin/release` сегодня СТРОКИ УДАЛЯЕТ, поэтому снять `admin` с живого
    # сервера нечем — ряд взят настоящий, подменено одно поле, и проверяется
    # ровно одно: незнакомая причина не читается как «вы сами остановили».
    foreign = copy.deepcopy(body)
    for row in foreign["instances"]:
        if row["instance_id"] == captured["released"]:
            row["released_by"] = "admin"
    freed = {row["instance_id"]: row
             for row in slotview.describe(foreign, now)["rows"]}[captured["released"]]
    check("причина освобождения, которой витрина не знает, названа, а не выдана за остановку",
          "admin" in freed["pill"] and "ОСТАНОВЛЕН" not in freed["pill"],
          freed["pill"])

    silent = slotview.unknown()
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

    global CAPTURE
    CAPTURE = _capture()
    _payload_checks()
    _unit_checks()

    captured = CAPTURE["slots"]
    licensing_port, site_port = _free_port(), _free_port()
    stub = HTTPServer(("127.0.0.1", licensing_port), _Stub)
    threading.Thread(target=stub.serve_forever, daemon=True).start()

    server, allowed = _start_site(licensing_port, site_port)
    base = f"http://127.0.0.1:{site_port}"
    admin_path = os.environ.get("PSEUDEX_ADMIN_PATH", "admin")
    alive_label = ""
    try:
        with sync_playwright() as pw:
            browser = _launch(pw)
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

            _sign_in(page, base, admin_path, _STAFF[_SLOT_ORG])
            check("вошёл паролем и кодом", "/login" not in page.url,
                  page.url.replace(base, ""))

            # --- КАБИНЕТ: четыре состояния контейнера на снятом теле ----
            #
            # Пятое состояние клиента — упёрся в потолок рабочих процессов —
            # живёт в другой организации и проверяется в конце файла: потолок
            # считается по организации целиком.
            page.goto(f"{base}/app/", wait_until="networkidle")
            body = page.inner_text("body")
            from billing import slots as slotview
            alive_label = slotview.ago(captured["instances"]["alive_seconds"])
            check("кабинет отрисован",
                  len(body) > 200 and "Traceback" not in body,
                  f"{len(body)} симв." + (f", ошибки: {errors[:2]}" if errors else ""))
            check("кабинет считает ЗАНЯТЫЕ слоты, а не строки списка",
                  f"1 из {allowed} занято" in body
                  and f"4 из {allowed} занято" not in body,
                  f"в тексте: {'есть 1 из' if f'1 из {allowed}' in body else 'НЕТ'}; "
                  f"{'ЕСТЬ 4 из' if f'4 из {allowed}' in body else 'нет 4 из'}")
            check("держащий слот назван живым и со сроком",
                  captured["holding"] in body and "ДЕРЖИТ СЛОТ" in body
                  and "если замолчит" in body)
            check("замолчавший контейнер назван молчащим, а слот его — свободным",
                  captured["silent"] in body and "МОЛЧИТ — СЛОТ СВОБОДЕН" in body,
                  "строка есть" if captured["silent"] in body else "строки нет")
            check("остановленный САМ не показан работающим и не назван отобранным",
                  captured["released"] in body and "ОСТАНОВЛЕН — СЛОТ СВОБОДЕН" in body
                  and "остановлен сам" in body)
            check("отобранное место названо отобранным, а не «вы сами остановили»",
                  captured["reclaimed"] in body
                  and "МЕСТО ОТОБРАНО — СЛОТ СВОБОДЕН" in body,
                  "строка есть" if captured["reclaimed"] in body else "строки нет")
            check("кабинет говорит, что будет с работающим контейнером, у которого забрали место",
                  "на следующем продлении аренды он получит отказ" in body
                  and "НА ТОМ ЖЕ ТОМЕ" in body)
            # СЛОВО РЯДОМ С ЧИСЛОМ. Строка отобранного контейнера говорила «его
            # МЕСТО занял другой контейнер», а под списком на том же экране
            # стояло «мест под потолком тарифа занято N» — и N включало ровно
            # эти места: молчание их не освобождает (Б26quinquies), другому
            # запуску достался СЛОТ. Клиент читал совет, который его же число
            # опровергает. То же у молчащего: «поднимайте новый» верно про слот
            # и неверно про места, а отказывает по местам (Б26sexies).
            taken_li = page.locator("li", has_text=captured["reclaimed"]).first.inner_text()
            silent_li = page.locator("li", has_text=captured["silent"]).first.inner_text()
            # Сдвиг времени на `held_places` не влияет — это счёт строк, а не
            # срок, — поэтому число берётся с тела как снято.
            held_total = slotview.describe(captured["instances"],
                                           captured["instances_at"])["held_places"]
            check("кабинет не называет отданным место, которое стоит в его же числе",
                  "его место занял другой контейнер" not in taken_li
                  and "СЛОТ занял другой контейнер" in taken_li
                  and (held_total or 0) > 0,
                  f"мест по экрану {held_total}; строка: {taken_li[:120]}")
            check("и не обещает у молчащего свободных мест, которых молчание не освобождает",
                  "МЕСТА его рабочих процессов молчание не освобождает" in silent_li,
                  silent_li[:160])
            check("а число мест под потолком стоит на том же экране, чтобы сверить",
                  f"под потолком тарифа занято {held_total}" in body,
                  f"мест {held_total}")
            # ТЕ САМЫЕ ЧИСЛА, ПО КОТОРЫМ ОТКАЗЫВАЕТ ПОТОЛОК. Клиент читает в
            # отказе «сейчас живых столько-то рабочих процессов» и до сих пор не
            # мог сверить это число ни с одним своим экраном.
            check("кабинет показывает живые процессы каждого контейнера",
                  f"рабочих процессов {captured['workers']['alive']}" in body)
            check("кабинет говорит, через сколько молчания слот освободится сам",
                  f"{alive_label} молчания" in body,
                  f"срок из alive_seconds сервера: {alive_label}")
            check("кабинет говорит, что переразвёртывание на том же томе слот не теряет",
                  "НА ТОМ ЖЕ ТОМЕ" in body and "pseudex-data:/data" in body)
            turnover = captured["instances"]["turnover_last_hour"]
            check("кабинет называет израсходованный бюджет перевыдач",
                  f"{turnover} раз" in body
                  and f"из {captured['instances']['turnover_budget']} допустимых" in body,
                  f"перевыдач {turnover} из {captured['instances']['turnover_budget']}")
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

            # --- ОТОБРАННЫЙ ЕЩЁ РАБОТАЕТ --------------------------------
            #
            # Второй снимок того же сервера, снятый после того, как отобранный
            # контейнер прислал отчёт. Клиенту это меняет действие: его движок
            # жив и встанет на следующем продлении.
            _MODE["instances"] = "echo"
            page.goto(f"{base}/app/", wait_until="networkidle")
            echo = page.inner_text("body")
            check("кабинет видит, что у отобранного контейнера движок ещё работает",
                  "он ещё отчитывается" in echo and "он ещё отчитывается" not in body,
                  "сказано только на втором снимке" if "он ещё отчитывается" in echo
                  else "НЕ СКАЗАНО")
            _MODE["instances"] = "snapshot"

            # --- КОНСОЛЬ: карточка клиента ------------------------------
            page.goto(f"{base}/{admin_path}/ops/{_SLOT_ORG}/", wait_until="networkidle")
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
                  f"{alive_label} молчания" in console
                  and f"{turnover} из {captured['instances']['turnover_budget']}" in console)
            # СТРОКА ЖИВОГО ИНСТАНСА ЦЕЛИКОМ: «столбец есть» на этой странице
            # проходило бы и на старом шаблоне (слово встречается в соседней
            # таблице), а утверждается здесь именно то, что в строке инстанса
            # стоят его живые процессы и версия его движка.
            alive_row = page.locator("tr", has_text=captured["holding"]).first.inner_text()
            check("в строке живого инстанса стоят его процессы и версия движка",
                  str(captured["workers"]["alive"]) in alive_row
                  and CAPTURE["engine_version"] in alive_row,
                  alive_row.replace("\n", " | "))
            taken_row = page.locator("tr", has_text=captured["reclaimed"]).first.inner_text()
            check("в строке отобранного места сказано, что будет дальше",
                  "409" in taken_row and "МЕСТО ОТОБРАНО" in taken_row,
                  taken_row.replace("\n", " | "))

            # --- КОНСОЛЬ: флот ------------------------------------------
            page.goto(f"{base}/{admin_path}/ops/", wait_until="networkidle")
            fleet = page.inner_text("body")
            check("флот показывает занятые слоты, а не длину списка аренд",
                  f"1 / {allowed}" in fleet and f"4 / {allowed}" not in fleet,
                  f"{'есть 1 /' if f'1 / {allowed}' in fleet else 'НЕТ 1 /'}; "
                  f"{'ЕСТЬ 4 /' if f'4 / {allowed}' in fleet else 'нет 4 /'}")

            # --- СЕРВЕР ОТВЕТИЛ, НО ЧИСЕЛ НЕ НАЗВАЛ ---------------------
            #
            # Именно так экраны и соврали: ноль пришёл не с сервера, а из
            # `get(key, 0)` витрины, и «0 из 1 занято» стояло при 128 живых
            # арендах. Ответ без полей — это вопрос без ответа, а не ноль.
            _MODE["instances"] = "thin"
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
            page.goto(f"{base}/{admin_path}/ops/{_SLOT_ORG}/", wait_until="networkidle")
            thin_console = page.inner_text("body")
            mute_row = page.locator("tr", has_text=captured["holding"]).first
            # КЛЕТКА, А НЕ СТРОКА: «нуля в строке нет» прошло бы и на нуле —
            # в той же строке стоит версия движка.
            mute_processes = mute_row.locator("td").nth(2).inner_text().strip()
            check("консоль пишет «не назвал» вместо нуля занятых",
                  "не назвал занятость" in thin_console
                  and "занято по тарифу 0" not in thin_console)
            check("в строке без чисел стоит прочерк, а не ноль процессов",
                  mute_processes == "—"
                  and "ЗАНЯТОСТЬ НЕИЗВЕСТНА" in mute_row.inner_text(),
                  f"клетка процессов: {mute_processes!r}")

            # --- МОЛЧАНИЕ СЕРВЕРА — ЭТО «НЕИЗВЕСТНО» --------------------
            _MODE["instances"] = "down"
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
            _MODE["instances"] = "snapshot"

            # --- ПОТОЛОК РАБОЧИХ ПРОЦЕССОВ ------------------------------
            #
            # Другая организация и другой человек: контейнер, у которого 32
            # живых воркера, и настоящий 409 на тридцать третьем. Клиент читает
            # в отказе число — и обязан найти его на своём экране.
            ceiling = CAPTURE["ceiling"]
            _sign_in(page, base, admin_path, _STAFF[_CEIL_ORG])
            check("вошёл вторым человеком, второй организации",
                  "/login" not in page.url, page.url.replace(base, ""))
            page.goto(f"{base}/app/", wait_until="networkidle")
            full = page.inner_text("body")
            row = ceiling["instances"]["instances"][0]
            check("кабинет упёршегося в потолок показывает те же числа, что и отказ",
                  f"рабочих процессов {row['live_processes']}" in full
                  and str(row["live_processes"]) in
                  ceiling["refusals"]["process_ceiling"]["detail"],
                  f"живых {row['live_processes']}")
            check("кабинет называет занятые места под потолком тарифа",
                  f"под потолком тарифа занято {row['held_places']}" in full,
                  f"мест {row['held_places']}")

            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
        stub.shutdown()

    print("\n" + ("ВСЁ ЗЕЛЁНОЕ" if not FAILURES else f"УПАЛО: {FAILURES}"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
