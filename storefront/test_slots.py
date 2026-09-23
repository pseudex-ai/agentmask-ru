"""ЭКРАН, КОТОРЫЙ ВРЁТ ПРО СЛОТ, — ЭТО ТОТ ЖЕ ДЕФЕКТ, ЧТО И СЛОТ, КОТОРЫЙ ДЕРЖИТ ТРУП.

Что здесь доказывается (Б26, Б26bis … Б26sexies; ТЗ «слоты, поколения и
фенсинг» §3.5, §9.4):

  * «занято» — это ЧИСЛО С СЕРВЕРА, а не длина списка. В ответе
    `/admin/instances` теперь есть и СВОБОДНЫЕ слоты; сложить его длиной значит
    написать «4 из 4 занято» человеку, у которого работают два контейнера;
  * состояние слота названо своим именем: занят, свободен, свободен и на нём
    ДОЦЕЖИВАЕТ прежнее поколение. Последнее — не «остановлен»: сервер знает,
    что это поколение больше не покупает ёмкость, и НЕ знает, работает ли оно;
  * слово рядом с числом не спорит с числом. Экран писал «слот уже свободен,
    поднимайте новый» в той же строке, где стояло «мест занято 32»;
  * молчание лицензионного сервера показано молчанием, а не нулём: «0 из 1
    занято» читается как ответ, и человек делает из него вывод, что
    контейнеров у него нет.

ЧЕГО ЗДЕСЬ БОЛЬШЕ НЕТ И ПОЧЕМУ. Состояний `silent` и `reclaimed`, чисел
`held_places`/`live_processes`, бюджета перевыдач и обещания «слот освободится
через N молчания» не осталось ни в одной проверке — вместе с механизмами,
которые их считали. Каждый из них лечил свой дефект (Б26: труп держал слот
сутки; Б26quater: поколение из 32 ключей переоткрывалось; Б26bis: бюджет был
единственным ограничителем карусели), и каждый лечится теперь тем, что сервер
не судит по молчанию вовсе: слот занимает поколение, которое выдали МЫ, а
перезапуск лишь поднимает его номер.

ПОЧЕМУ ЭТА ПРОВЕРКА ЕЗДИТ НА СНЯТОМ ТЕЛЕ (Б26quater, последний абзац).
Предыдущая ездила на теле, написанном рукой: в нём стояли поля, которых сервер
не отдаёт, и числа, которых он в этом состоянии не даёт. Проверка, собранная из
полей, которых сервер никогда не присылает, провалиться не может — она
охраняет фантазию автора. Тела СНИМАЮТСЯ с настоящего `licensing.devserver`
(`test_slots_stand.py`): организацию доводят до каждого состояния настоящими
вызовами `/v1/lease`, `/v1/meter`, `/v1/release`, `/admin/release`, а 409
`fenced` снимается тем же прогоном.

ЧТО ОСТАЛОСЬ ЗАГЛУШКОЙ И ПОЧЕМУ. Тела отдаёт локальный HTTP-стенд, а не сам
лицензионный сервер: снимок — это байты сервера в тот момент, когда все
состояния существовали разом. Заглушка ничего не вычисляет, она отдаёт снятые
байты по тому же пути и через тот же коннектор (`billing/licensing.py`), то
есть цепочка «ответ ручки → коннектор → вьюха → шаблон» проверяется целиком.
Два вырожденных случая — сервер не ответил и сервер ответил без чисел —
получены ВЫЧИТАНИЕМ полей из настоящего тела: так выглядит ответ версии старше
витрины, и подставить здесь ноль значило бы подписаться числом под тем, чего
сервер не говорил.

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
# Две организации и два человека: одна на тарифе с запасом (там видно и
# занятый слот, и свободный, и доцеживающее поколение), вторая на тарифе в ОДИН
# слот — там и только там перезапуск вытесняет предыдущее поколение, потому что
# свободного слота для него нет. Кабинет показывает организацию по старшему
# членству, значит у второй организации свой вход.
_SLOT_ORG, _FENCE_ORG = "slotco", "fenceco"
_STAFF = {_SLOT_ORG: "slots@pseudex.local", _FENCE_ORG: "fenced@pseudex.local"}
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


def _migrating(body: dict) -> dict:
    """СРАЗУ ПОСЛЕ ПЛАТФОРМЕННОГО РЕЛИЗА: слотов не занято ни одного, а
    контейнеры работают.

    Миграция намеренно не назначает держателей — установка выпущенного движка
    чеканится на каждый старт контейнера, поэтому усыновление отдавало слот
    каждому мёртвому перезапуску и печатало «занято 4 из 4» клиенту с одним
    контейнером. Обратная сторона: несколько часов занятость ниже фактической,
    и «0 из 4» без единого слова читается как ОТВЕТ «у вас ничего не работает»
    — догадка того же рода, только в другую сторону. Сервер называет число
    установок, ещё не занявших слот; экран обязан его показать.
    """
    view = copy.deepcopy(body)
    view["occupied"] = 0
    view["pending_installations"] = 3
    for row in view.get("slots", []):
        row["holder"] = None
        row["draining"] = []
    return view


def _thin(body: dict) -> dict:
    """ОТВЕТ БЕЗ ЧИСЕЛ — ВЫЧИТАНИЕМ ИЗ НАСТОЯЩЕГО, а не выдумкой.

    Сервер ответил, но `occupied`, `slot_count`, счётчиков за сутки не назвал, а
    у держателя не назвал ни воркеров, ни времени последней покупки. Так
    выглядит ответ версии старше витрины, урезанный прокси или сломанный на той
    стороне — и ровно так экраны и соврали: ноль пришёл не с сервера, а из
    `get(key, 0)` витрины.
    """
    thin = copy.deepcopy(body)
    for field in ("occupied", "slot_count", "generations_24h",
                  "epochs_unacked_24h", "slot_contention_24h",
                  "processes_per_instance", "pending_installations"):
        thin.pop(field, None)
    rows = [row for row in thin.get("slots", []) if row.get("holder")][:1]
    for row in rows:
        for field in ("workers_heard", "last_purchase_at"):
            row["holder"].pop(field, None)
    thin["slots"] = rows
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
    for row in shifted.get("slots", []):
        holder = row.get("holder") or {}
        for field in ("since", "last_heard_at", "last_purchase_at"):
            if holder.get(field):
                holder[field] = holder[field] + delta
        for gone in row.get("draining", []):
            if gone.get("fenced_at"):
                gone["fenced_at"] = gone["fenced_at"] + delta
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
        if org_id == _FENCE_ORG:
            captured = CAPTURE["fenced"]
            return 200, _shift(captured["instances"], captured["instances_at"])
        captured = CAPTURE["slots"]
        body = _shift(captured["instances"], captured["instances_at"])
        if mode == "thin":
            return 200, _thin(body)
        if mode == "migrating":
            return 200, _migrating(body)
        return 200, body

    def do_GET(self) -> None:  # noqa: N802 — имя задано базовым классом
        path, _, query = self.path.partition("?")
        org_id = ""
        for pair in query.split("&"):
            if pair.startswith("org_id="):
                org_id = pair.split("=", 1)[1]
        if _MODE["instances"] == "down" and path != "/admin/plans":
            self._send(503, {"error": "down"})
            return
        captured = CAPTURE["fenced"] if org_id == _FENCE_ORG else CAPTURE["slots"]
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
# КАЖДОЙ ОРГАНИЗАЦИИ — ЕЁ ТАРИФ. Один общий давал кабинету «1 из 4 занято» там,
# где сервер назвал один слот: экран печатал число ВИТРИНЫ вместо числа сервера,
# и проверка ловила это как расхождение (Б26bis — число с сервера, а не своё).
plans = {os.environ["SLOT_ORG"]: Plan.objects.get(code=os.environ["PLAN_CODE"]),
         os.environ["FENCE_ORG"]: Plan.objects.get(code=os.environ["FENCE_PLAN_CODE"])}
plan = plans[os.environ["SLOT_ORG"]]

# ОДИН ЧЕЛОВЕК НА ОБА ЭКРАНА СВОЕЙ ОРГАНИЗАЦИИ. Кабинет открывается по членству,
# консоль — по признаку сотрудника и второму фактору; один вход вместо двух
# проверяет ровно то, что проверяется, и не заводит второй способ входа.
for org_id, display, email in ((os.environ["SLOT_ORG"], "ООО Слот", os.environ["SLOT_EMAIL"]),
                              (os.environ["FENCE_ORG"], "ООО Фенс", os.environ["FENCE_EMAIL"])):
    staff = User.objects.create_user(email=email, password=os.environ["STAFF_PASSWORD"])
    staff.is_staff = staff.is_superuser = True
    staff.save()
    TOTPDevice.objects.create(user=staff, name="slots", confirmed=True,
                              key=os.environ["STAFF_TOTP_KEY"])
    org = Organization.objects.create(id=org_id, display_name=display,
                                      legal_name=display, inn="7707083893")
    Membership.objects.create(user=staff, organization=org)
    Subscription.objects.create(organization=org, plan=plans[org_id],
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
        "FENCE_ORG": _FENCE_ORG,
        "SLOT_EMAIL": _STAFF[_SLOT_ORG],
        "FENCE_EMAIL": _STAFF[_FENCE_ORG],
        # ТОТ ЖЕ ТАРИФ, ЧТО У ЛИЦЕНЗИОННОГО СЕРВЕРА: «занято 1 из 1» — это его
        # число рядом с нашим, и разные тарифы по две стороны экрана читались бы
        # как ошибка счёта.
        "PLAN_CODE": CAPTURE["slots"]["plan"],
        "FENCE_PLAN_CODE": CAPTURE["fenced"]["plan"],
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
    рукой, и поля в нём были выдумкой автора. Если сервер перестанет называть
    держателя или остаток отфенсенного, падать обязано ЗДЕСЬ — с именем поля, —
    а не в виде зелёной страницы, на которой доцеживающее поколение названо
    остановленным.
    """
    slots = CAPTURE["slots"]
    body = slots["instances"]
    by_number = {row["slot_no"]: row for row in body["slots"]}
    held = {row["holder"]["installation_id"]: row for row in body["slots"]
            if row["holder"]}
    check("снятое тело описывает ЧЕТЫРЕ состояния слота",
          len(body["slots"]) == 4
          and set(held) == {slots["holding"], slots["released"]}
          and any(row["draining"] for row in body["slots"])
          and any(not row["holder"] and not row["draining"]
                  for row in body["slots"]),
          f"держат: {sorted(held)}; "
          f"доцеживают: {[r['slot_no'] for r in body['slots'] if r['draining']]}")
    check("занято — ЧИСЛО СЕРВЕРА, и оно не равно длине списка",
          body["occupied"] == 2 and len(body["slots"]) == 4,
          f"занято {body['occupied']} при {len(body['slots'])} строках")
    check("сервер называет держателя поимённо: поколение, том, версия, покупка",
          {"start_id", "installation_id", "engine_version", "since",
           "workers_heard", "last_purchase_at", "released"}
          <= set(held[slots["holding"]]["holder"]),
          f"{sorted(held[slots['holding']]['holder'])}")
    check("прощание ЗАПИСАНО и отличает остановленного от работающего",
          held[slots["released"]]["holder"]["released"] is True
          and held[slots["holding"]]["holder"]["released"] is False,
          "и при этом СЛОТ остаётся за ним: решения `/v1/release` не читают")
    drained = next(row for row in body["slots"] if row["draining"])
    check("доцеживающее поколение названо со своим эпохом, причиной и остатком",
          drained["draining"][0]["epoch"] < drained["epoch"]
          and drained["draining"][0]["fenced_by"] == "admin"
          and drained["draining"][0]["band_left_estimate"] > 0,
          f"{drained['draining'][0]}")
    refusal = slots["refusals"]["fenced_by_admin"]
    check("отказ настоящий, 409 `fenced`, и называет РЫЧАГ, а не несуществующего соседа",
          refusal["status"] == 409 and refusal["error"] == "fenced"
          and "поддержка" in refusal["detail"]
          and "занял более новый запуск" not in refusal["detail"],
          refusal["detail"][:110])

    fenced = CAPTURE["fenced"]
    claim = fenced["refusals"]["fenced_by_claim"]
    check("а перезапуск на полном тарифе фенсит предыдущее поколение, не отказывая аренде",
          fenced["epochs"]["second"] == fenced["epochs"]["first"] + 1
          and claim["status"] == 409 and claim["error"] == "fenced",
          f"эпохи {fenced['epochs']}, отказ {claim['status']} {claim['error']}")
    check("и код отказа НЕ `instance_limit` — иначе выпущенный флот гаснет, а не доцеживает",
          claim["error"] != "instance_limit",
          "instance_limit ∈ _ANSWER_CODES движка → _expire() в ту же секунду (Б30)")


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
    # «СЕЙЧАС» — ЭТО МОМЕНТ СЪЁМКИ. Тело абсолютное, сроки относительные;
    # считать его по часам этого прогона значило бы состарить снимок на время
    # работы стенда и мерить не то.
    now = captured["instances_at"]
    view = slotview.describe(body, now)
    rows = {row["slot_no"]: row for row in view["rows"]}
    check("занято берётся у сервера, а не из длины списка",
          view["occupied"] == body["occupied"] == 2 and len(view["rows"]) == 4,
          f"occupied={view['occupied']} строк={len(view['rows'])}")
    holding = next(row for row in view["rows"]
                   if row["installation_id"] == captured["holding"])
    freed = next(row for row in view["rows"] if row["draining"])
    empty = next(row for row in view["rows"]
                 if not row["held"] and not row["draining"])
    check("занятый слот назван занятым, свободный — свободным",
          holding["held"] is True and holding["pill"] == "ЗАНЯТ"
          and empty["held"] is False and empty["pill"] == "СВОБОДЕН",
          f"{holding['pill']!r} / {empty['pill']!r}")
    check("пояснение собрано ЗДЕСЬ и несёт поколение, воркеров и покупку",
          f"поколение {holding['epoch']}" in holding["note"]
          and f"воркеров слышно {captured['workers']['live']}" in holding["note"]
          and "ёмкость покупал" in holding["note"],
          holding["note"])
    check("доцеживающее поколение названо и его остаток подписан «до»",
          freed["draining"] and freed["draining"][0]["band_left"] > 0
          and freed["draining"][0]["fenced_by"] == "освободила поддержка",
          f"{freed['draining']}")
    check("слово рядом с числом не спорит с числом: свободный слот НЕ пустой",
          freed["held"] is False and freed["pill"] == "СВОБОДЕН"
          and freed["note"] == "свободен" and bool(freed["draining"]),
          "слот свободен, и на нём доцеживает прежнее поколение — это две "
          "разные вещи, и экран говорит обе")

    # ── ОТВЕТ БЕЗ ЧИСЕЛ. Поле, которого нет, — это «сервер не назвал».
    thin = slotview.describe(_thin(body), now)
    mute = thin["rows"][0]
    check("занятость, которой сервер не назвал, — не ноль",
          thin["occupied"] is None and thin["slot_count"] is None,
          f"{thin['occupied']!r} из {thin['slot_count']!r}")
    check("запусков за сутки, которых сервер не назвал, — не ноль",
          thin["generations_24h"] is None and thin["contention"] is None,
          f"{thin['generations_24h']!r}/{thin['contention']!r}")
    # ЧЕРЕЗ `.get`, А НЕ ПО КЛЮЧУ: витрина, которая поле ПОТЕРЯЛА, обязана
    # дать здесь красную строку с именем поля, а не KeyError посреди прогона.
    check("воркеры, которых сервер не назвал, — не ноль",
          mute.get("workers_heard", 0) is None
          and "воркеров сервер не назвал" in mute.get("note", ""),
          f"{mute.get('workers_heard', 'нет поля')!r}: {mute.get('note', '')}")
    check("и покупка, которой не было, названа отсутствием, а не нулевой датой",
          "ёмкость ещё не покупал" in mute["note"], mute["note"])

    silent = slotview.unknown()
    check("молчание сервера — это «неизвестно», а не ноль",
          silent["known"] is False and silent["occupied"] is None
          and silent["rows"] == [],
          f"known={silent['known']} occupied={silent['occupied']!r}")

    # ── КАБИНЕТ И КОНСОЛЬ ЧИТАЮТ ОДНО И ТО ЖЕ. Плашку и пояснение собирает
    # ОДНА функция, и это не экономия: два шаблона, ветвящихся каждый сам,
    # писали про один контейнер «ОСТАНОВЛЕН» и «ОТПУЩЕН» (Б26bis).
    fenced_view = slotview.describe(CAPTURE["fenced"]["instances"],
                                    CAPTURE["fenced"]["instances_at"])
    check("на полном тарифе занято равно числу слотов, и держатель один",
          fenced_view["occupied"] == fenced_view["slot_count"] == 1
          and len(fenced_view["rows"][0]["draining"]) == 1,
          f"{fenced_view['occupied']} из {fenced_view['slot_count']}")


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
    try:
        with sync_playwright() as pw:
            browser = _launch(pw)
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

            _sign_in(page, base, admin_path, _STAFF[_SLOT_ORG])
            check("вошёл паролем и кодом", "/login" not in page.url,
                  page.url.replace(base, ""))

            # --- КАБИНЕТ: четыре состояния слота на снятом теле ---------
            page.goto(f"{base}/app/", wait_until="networkidle")
            body = page.inner_text("body")
            from billing import slots as slotview
            view = slotview.describe(captured["instances"],
                                     captured["instances_at"])
            holding = next(row for row in view["rows"]
                           if row["installation_id"] == captured["holding"])
            freed = next(row for row in view["rows"] if row["draining"])
            check("кабинет отрисован",
                  len(body) > 200 and "Traceback" not in body,
                  f"{len(body)} симв." + (f", ошибки: {errors[:2]}" if errors else ""))
            # ЗАНЯТО — ЧИСЛО СЕРВЕРА, А НЕ ДЛИНА СПИСКА. В списке теперь есть и
            # свободные слоты; сложить его длиной значило бы написать «4 из 4
            # занято» человеку, у которого работают два контейнера.
            check("кабинет считает ЗАНЯТЫЕ слоты, а не строки списка",
                  f"{view['occupied']} из {allowed} занято" in body
                  and f"{len(view['rows'])} из {allowed} занято" not in body,
                  f"занято {view['occupied']} при {len(view['rows'])} строках")
            check("каждый слот назван номером и поколением",
                  f"слот {holding['slot_no']}" in body
                  and f"поколение {holding['epoch']}" in body,
                  f"слот {holding['slot_no']}, поколение {holding['epoch']}")
            check("занятый слот назван занятым, свободный — свободным",
                  "ЗАНЯТ" in body and "СВОБОДЕН" in body)
            check("держатель назван томом, версией движка и временем ПОКУПКИ ёмкости",
                  captured["holding"] in body
                  and CAPTURE["engine_version"] in body
                  and "ёмкость покупал" in body,
                  "покупка — это нижняя граница «живых», единственная, которую "
                  "теорема нам оставляет")
            check("воркеры названы числом сервера, а не догадкой экрана",
                  f"воркеров слышно {captured['workers']['live']}" in body,
                  f"воркеров {captured['workers']['live']}")
            # СЛОВО РЯДОМ С ЧИСЛОМ. Экран писал «слот уже свободен, поднимайте
            # новый» в той же строке, где стояло «мест занято 32». Здесь обе
            # вещи говорятся и не спорят: слот свободен И на нём доцеживает
            # прежнее поколение, у которого остался КУПЛЕННЫЙ остаток.
            drained_li = page.locator(
                "li", has_text=f"слот {freed['slot_no']}").first.inner_text()
            check("про доцеживающее поколение сказано ОБЕ вещи и без противоречия",
                  "СВОБОДЕН" in drained_li
                  and "доработает на уже купленном" in drained_li
                  and str(freed["draining"][0]["band_left"]) in drained_li,
                  drained_li.replace("\n", " | ")[:160])
            check("и оно НЕ названо остановленным — этого мы не знаем",
                  "остановлен" not in drained_li.lower()
                  or "остановится само" in drained_li,
                  drained_li.replace("\n", " | ")[:160])
            # ЧЕГО НА ЭКРАНЕ БОЛЬШЕ НЕТ И БЫТЬ НЕ ДОЛЖНО: обещания «слот
            # освободится через N молчания» (это было суждение о том, жив ли
            # контейнер) и бюджета перевыдач (его больше не существует).
            check("кабинет не обещает освобождения по молчанию и не называет бюджет",
                  "молчания" not in body and "перевыдач" not in body
                  and "допустимых в час" not in body,
                  "оба обещания сняты вместе с механизмами, которые их держали")
            check("зато сказано, что перезапуск ничего не ждёт и не стоит",
                  "Перезапуск контейнера ничего не стоит и ничего не ждёт" in body
                  and "OOM" in body,
                  "OOM-килл и docker stop идут одним путём")
            check("и назван счётчик запусков за сутки — он ничего не запрещает",
                  f"Запусков за сутки {view['generations_24h']}" in body,
                  f"{view['generations_24h']}")
            # ВЕТКИ УДАЛЁННЫХ СОСТОЯНИЙ — ПО ИСХОДНИКУ, А НЕ ПО ЭКРАНУ: сервер
            # их больше не отдаёт, поэтому ветка по ним просто не сработает, и
            # проверка отрисованного прошла бы и на старом шаблоне.
            # КОММЕНТАРИЙ — НЕ ВЕТКА. Имена удалённых состояний в
            # `{% comment %}` — это запись о том, что и почему ушло; удалять её
            # ради зелёной проверки значило бы стереть память шести заходов
            # (Б26 … Б26sexies). Проверяется РАЗМЕТКА, поэтому комментарии
            # вырезаются, а всё остальное — включая любой `{% if %}` — нет.
            _comment = re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}",
                                  re.DOTALL)
            stale = sorted({f"{path.relative_to(_ROOT)}:{word}"
                            for path in (_ROOT / "templates").rglob("*.html")
                            for word in ("cooling", "reclaimed", "held_places",
                                         "live_processes", "turnover")
                            if word in _comment.sub("", path.read_text())})
            check("ни один шаблон витрины не ветвится по удалённым состояниям",
                  not stale, f"осталось: {stale}")

            # --- КОНСОЛЬ: карточка клиента ------------------------------
            page.goto(f"{base}/{admin_path}/ops/{_SLOT_ORG}/", wait_until="networkidle")
            console = page.inner_text("body")
            check("карточка клиента отрисована",
                  len(console) > 200 and "Traceback" not in console,
                  f"{len(console)} симв.")
            check("консоль показывает занято числом сервера",
                  f"занято {view['occupied']} из {view['slot_count']}" in console,
                  f"занято {view['occupied']} из {view['slot_count']}")
            # ОДНО СЛОВО ПРО ОДИН СЛОТ НА ОБОИХ ЭКРАНАХ. Поддержка и клиент
            # смотрят на один слот и обязаны видеть одну плашку; различаться
            # должно объяснение вокруг неё, а не имя состояния (Б26bis).
            check("кабинет и консоль рисуют один слот ОДНОЙ плашкой",
                  console.count("ЗАНЯТ") >= view["occupied"]
                  and "ЗАНЯТ" in body and "СВОБОДЕН" in console,
                  "плашку собирает billing/slots.py, а не два шаблона порознь")
            alive_row = page.locator(
                "tr", has_text=captured["holding"]).first.inner_text()
            check("в строке слота стоят его том, воркеры и версия движка",
                  captured["holding"] in alive_row
                  and str(captured["workers"]["live"]) in alive_row
                  and CAPTURE["engine_version"] in alive_row,
                  alive_row.replace("\n", " | "))
            drained_row = page.locator(
                "tr", has_text=str(freed["draining"][0]["start_id"])).first.inner_text()
            check("в строке свободного слота сказано, что на нём доцеживает",
                  "отфенсено" in drained_row and "встанет само" in drained_row,
                  drained_row.replace("\n", " | ")[:160])

            # --- КОНСОЛЬ: флот ------------------------------------------
            page.goto(f"{base}/{admin_path}/ops/", wait_until="networkidle")
            fleet = page.inner_text("body")
            check("флот показывает занятые слоты, а не длину списка",
                  f"{view['occupied']} / {allowed}" in fleet
                  and f"{len(view['rows'])} / {allowed}" not in fleet,
                  f"{view['occupied']} / {allowed}")

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
                  f"{'сказано' if 'не назвал занятость' in thin else 'НЕ СКАЗАНО'}")
            check("кабинет не подставляет ноль за не названных воркеров",
                  "воркеров сервер не назвал" in thin
                  and "воркеров слышно 0" not in thin)
            page.goto(f"{base}/{admin_path}/ops/{_SLOT_ORG}/", wait_until="networkidle")
            thin_console = page.inner_text("body")
            mute_row = page.locator("tr", has_text=captured["holding"]).first
            # КЛЕТКА, А НЕ СТРОКА: «нуля в строке нет» прошло бы и на нуле —
            # в той же строке стоит номер слота.
            mute_workers = mute_row.locator("td").nth(3).inner_text().strip()
            check("консоль пишет «не назвал» вместо нуля занятых",
                  "не назвал занятость" in thin_console
                  and "занято 0 из" not in thin_console)
            check("в строке без чисел стоит прочерк, а не ноль воркеров",
                  mute_workers == "—", f"клетка воркеров: {mute_workers!r}")

            # --- СРАЗУ ПОСЛЕ ПЛАТФОРМЕННОГО РЕЛИЗА ----------------------
            #
            # Занято ноль, а контейнеры работают: миграция не назначает
            # держателей, потому что перезапуски выпущенного флота от живых
            # контейнеров неотличимы. Голый ноль здесь — такая же догадка, как
            # «занято 4 из 4» с призраками, и краснеет это снятием
            # `pending_installations` из ответа или из витрины.
            _MODE["instances"] = "migrating"
            page.goto(f"{base}/app/", wait_until="networkidle")
            migrating = page.inner_text("body")
            check("кабинет объясняет ноль занятых сразу после релиза, а не молчит",
                  "0 из" in migrating and "прошлого релиза" in migrating
                  and "3 контейнер" in migrating,
                  next((line for line in migrating.splitlines()
                        if "прошлого релиза" in line), "НИ СЛОВА"))
            page.goto(f"{base}/{admin_path}/ops/{_SLOT_ORG}/",
                      wait_until="networkidle")
            migrating_console = page.inner_text("body")
            check("и консоль поддержки говорит то же самое теми же словами",
                  "прошлого релиза" in migrating_console,
                  next((line for line in migrating_console.splitlines()
                        if "прошлого релиза" in line), "НИ СЛОВА"))

            # --- МОЛЧАНИЕ СЕРВЕРА — ЭТО «НЕИЗВЕСТНО» --------------------
            _MODE["instances"] = "down"
            page.goto(f"{base}/app/", wait_until="networkidle")
            offline = page.inner_text("body")
            check("кабинет открывается, когда лицензионный сервер молчит",
                  len(offline) > 200 and "Traceback" not in offline,
                  f"{len(offline)} симв.")
            check("молчание сервера показано молчанием, а не нулём занятых слотов",
                  "неизвестно" in offline and f"0 из {allowed} занято" not in offline,
                  f"{'сказано' if 'неизвестно' in offline else 'НЕ СКАЗАНО'}")
            page.goto(f"{base}/{admin_path}/ops/", wait_until="networkidle")
            offline_fleet = page.inner_text("body")
            check("флот на молчащем сервере пишет «?», а не ноль занятых",
                  f"? / {allowed}" in offline_fleet
                  and f"0 / {allowed}" not in offline_fleet,
                  f"{'есть ?' if f'? / {allowed}' in offline_fleet else 'НЕТ ?'}")
            _MODE["instances"] = "snapshot"

            # --- ПОЛНЫЙ ТАРИФ: ПЕРЕЗАПУСК ВЫТЕСНЯЕТ ПРЕДЫДУЩЕЕ ----------
            #
            # Другая организация и другой человек: тариф в ОДИН слот, где
            # перезапуск и есть смена поколения. Клиент читает в отказе своего
            # движка «место занял более новый запуск» — и обязан найти на своём
            # экране и это поколение, и остаток предыдущего.
            fenced = CAPTURE["fenced"]
            _sign_in(page, base, admin_path, _STAFF[_FENCE_ORG])
            check("вошёл вторым человеком, второй организации",
                  "/login" not in page.url, page.url.replace(base, ""))
            page.goto(f"{base}/app/", wait_until="networkidle")
            full = page.inner_text("body")
            fenced_view = slotview.describe(fenced["instances"],
                                            fenced["instances_at"])
            gone = fenced_view["rows"][0]["draining"][0]
            check("кабинет показывает НОВОЕ поколение на том же слоте",
                  f"поколение {fenced['epochs']['second']}" in full
                  and "1 из 1 занято" in full,
                  f"эпох {fenced['epochs']['second']}")
            check("и отфенсенное предыдущее — с остатком, а не как остановленное",
                  f"предыдущее поколение {gone['epoch']}" in full
                  and "доработает на уже купленном" in full,
                  f"остаток до {gone['band_left']}")
            check("а отказ, который движок пишет в лог, называет то же событие",
                  "занял более новый запуск" in
                  fenced["refusals"]["fenced_by_claim"]["detail"],
                  fenced["refusals"]["fenced_by_claim"]["detail"][:90])

            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
        stub.shutdown()

    print("\n" + ("ВСЁ ЗЕЛЁНОЕ" if not FAILURES else f"УПАЛО: {FAILURES}"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
