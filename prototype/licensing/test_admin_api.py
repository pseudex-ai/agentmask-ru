"""АТАКИ ЧЕРЕЗ HTTP, А НЕ МИМО НЕГО.

    cd prototype && python3 licensing/test_admin_api.py

`test_metering_attacks.py` зовёт `LicenseStore` напрямую и НИ РАЗУ не ходит по
ручкам. Поэтому целый класс дефектов был ему структурно недоступен, и все они
жили в дереве до тех пор, пока их не нашли руками на живом стенде:

  * `/admin/resume` не был в белом списке — клиент платил, обслуживание не
    возвращалось, счёт оставался `draft`;
  * `int(usage.get("requests"))` без проверки — чужой мусор в теле давал нам
    500, а 500 у клиента grace-worthy;
  * нечисловое значение в `entities` роняло `/admin/usage` НАВСЕГДА;
  * битый `pubkey` разваливался внутри `seal()` — та же пятисотка другой
    дверью.

Здесь поднимаются НАСТОЯЩИЕ `server.app` и `server.admin_app` через
`TestClient`: без портов, но и без единого двойника. Токены выставляются ДО
импорта, потому что сервер читает их на импорте.
"""

import os
import sys
import tempfile
import time

os.environ.setdefault("PSEUDEX_LICENSE_DB", tempfile.mktemp(suffix=".db"))
os.environ["PSEUDEX_LICENSE_ADMIN_TOKEN"] = "test-admin"
os.environ["PSEUDEX_LICENSE_STOREFRONT_TOKEN"] = "test-shop"
sys.path.insert(0, ".")

from fastapi.testclient import TestClient  # noqa: E402

from licensing import server  # noqa: E402
from pseudex.bundle import generate_process_key  # noqa: E402

public = TestClient(server.app)
admin = TestClient(server.admin_app)
ADMIN = {"Authorization": "Bearer test-admin"}
SHOP = {"Authorization": "Bearer test-shop"}

fails: list[str] = []


def check(name: str, held: bool, detail: str = "") -> None:
    print(f"  {'ДЕРЖИТ ' if held else 'СЛОМАНО'} {name}   {detail}")
    if not held:
        fails.append(name)


# --- АВТОРИЗАЦИЯ: КАЖДАЯ РУЧКА × ЧЕТЫРЕ УЧЁТКИ ---------------------------
# Утверждается ТОЛЬКО код авторизации, поэтому телом годится `{}` и не нужно
# изобретать валидные данные под каждую ручку. Эта таблица поймала бы дефект
# `/admin/resume` в день его появления.
print("АВТОРИЗАЦИЯ АДМИНКИ")
wrong_audience, wrong_code = [], []
for action in server.ADMIN_ACTIONS:
    def call(headers: dict) -> object:
        if action.method == "GET":
            return admin.get(action.path, headers=headers)
        return admin.post(action.path, json={}, headers=headers)

    anon = call({})
    alien = call({"Authorization": "Bearer nope"})
    shop = call(SHOP)
    full = call(ADMIN)
    if anon.status_code != 401 or alien.status_code != 401:
        wrong_code.append(f"{action.path} anon={anon.status_code} alien={alien.status_code}")
    if full.status_code in (401, 403):
        wrong_code.append(f"{action.path} полный токен -> {full.status_code}")
    if action.storefront and shop.status_code == 403:
        wrong_audience.append(f"{action.path} закрыт для витрины")
    if not action.storefront and shop.status_code != 403:
        wrong_audience.append(f"{action.path} ОТКРЫТ витрине")

check("без токена и с чужим токеном — всегда 401", not wrong_code,
      str(wrong_code) if wrong_code else f"проверено {len(server.ADMIN_ACTIONS) * 4} обращений")
check("аудитория каждой ручки совпадает с объявленной", not wrong_audience,
      str(wrong_audience) if wrong_audience
      else f"проверено {len(server.ADMIN_ACTIONS)} ручек")

# Разъезд поверхности роняет старт, а не обнаруживается по жалобе клиента.
declared = server.ADMIN_ACTIONS
server.ADMIN_ACTIONS = declared + (server.AdminAction("/admin/ghost", "POST", True),)
try:
    server._check_admin_surface()
    caught = False
except RuntimeError:
    caught = True
finally:
    server.ADMIN_ACTIONS = declared
check("объявленная, но не смонтированная ручка роняет старт", caught)


# --- ВХОД: НИ ОДНОГО 5xx НА МУСОРЕ КЛИЕНТА -------------------------------
print("\nВХОД ЛИЦЕНЗИОННОГО СЕРВЕРА")
key = admin.post("/admin/issue", json={"org_id": "v", "plan": "start"},
                 headers=ADMIN).json()["key"]
recipient = generate_process_key().public

garbage_bodies = ["not-json", "[1,2,3]", "5", '"x"', "", "{"]
garbage_reports = [
    {"requests": "abc"}, {"requests": -1}, {"requests": True},
    {"requests": 2 ** 60}, {"values": None}, {"seq": "1"},
    {"entities": "PHONE"}, {"entities": {"PHONE": "many"}},
    {"entities": {"PHONE": -1}}, {"entities": {"P" * 200: 1}},
    {"entities": {str(n): 1 for n in range(300)}},
    {"prev": 5}, {"signature": []}, {"build": "b" * 10000},
]
fivehundreds = []
for body in garbage_bodies:
    for path in ("/v1/lease", "/v1/usage", "/v1/release"):
        code = public.post(path, content=body,
                           headers={"content-type": "application/json"}).status_code
        if code >= 500:
            fivehundreds.append(f"{path} <- {body[:12]!r} = {code}")
for report in garbage_reports:
    for path, extra in (("/v1/lease", {"pubkey": recipient, "engine_version": "1.0.0"}),
                        ("/v1/usage", {})):
        code = public.post(path, json={"key": key, "instance_id": "i",
                                       "usage": report, **extra}).status_code
        if code >= 500:
            fivehundreds.append(f"{path} <- {str(report)[:30]} = {code}")
for bad_key in ("", "age1x", "not-a-key", "a" * 5000):
    code = public.post("/v1/lease", json={"key": key, "instance_id": "i",
                                          "pubkey": bad_key,
                                          "engine_version": "1.0.0"}).status_code
    if code >= 500:
        fivehundreds.append(f"/v1/lease <- pubkey={bad_key[:10]!r} = {code}")

probes = len(garbage_bodies) * 3 + len(garbage_reports) * 2 + 4
check("ни один вход клиента не становится нашей пятисоткой", not fivehundreds,
      str(fivehundreds[:3]) if fivehundreds else f"проверено {probes} обращений")

check("тело сверх предела — 413, а не память",
      public.post("/v1/lease", content='{"pad":"' + "a" * 200000 + '"}',
                  headers={"content-type": "application/json"}).status_code == 413)

# ОТЧЁТ НА /v1/usage — ЭТО ВЕСЬ СМЫСЛ ЗАПРОСА, поэтому неразобранный там 400.
check("неразобранный отчёт на /v1/usage — это 400 с причиной",
      public.post("/v1/usage", json={"key": key, "instance_id": "i",
                                     "usage": {"requests": -5}}).status_code == 400)

# А НА /v1/lease — ОТБРАСЫВАЕТСЯ, И АРЕНДА ВЫДАЁТСЯ. Спор о биллинге не имеет
# права останавливать конечного пользователя.
# Своя организация: у "v" тариф «Старт» = один инстанс, и слот уже занят
# мусорным циклом выше. Отказ там был бы работой `may_lease`, а не дефектом.
renew_key = admin.post("/admin/issue", json={"org_id": "r", "plan": "start"},
                       headers=ADMIN).json()["key"]
renewer = generate_process_key().public
first = public.post("/v1/lease", json={"key": renew_key, "instance_id": "j",
                                       "pubkey": renewer,
                                       "engine_version": "1.0.0"})
renewed = public.post("/v1/lease", json={
    "key": renew_key, "instance_id": "j", "pubkey": renewer,
    "engine_version": "1.0.0",
    "lease_id": first.json()["lease_id"], "usage": {"requests": "abc"}})
totals = admin.get("/admin/usage", params={"org_id": "r"}, headers=ADMIN).json()["usage"]
check("испорченный отчёт не роняет аренду и не проходит тишиной",
      renewed.status_code == 200 and "bundle" in renewed.json()
      and totals["requests"] == 0 and totals["malformed_reports"] > 0,
      f"аренда={renewed.status_code} requests={totals['requests']} "
      f"malformed={totals['malformed_reports']}")

# ОТРАВЛЕНИЕ ИТОГОВ. Раньше одна такая строка делала /admin/usage вечной
# пятисоткой, и вместе с ним падали кабинет и выставление счёта.
server.STORE.record_usage("v", "poisoned", 1, {"PHONE": 1}, 1, seq=1, prev="",
                          signature="s", trust="signed", report_pubkey="pk")
with server.STORE._lock:
    server.STORE._conn.execute(
        "UPDATE usage SET entities=? WHERE org_id='v' AND instance_id='poisoned'",
        ('{"PHONE": "many", "NAME": 2}',))
    server.STORE._conn.commit()
after = admin.get("/admin/usage", params={"org_id": "v"}, headers=ADMIN)
check("отравленная строка не делает итоги недоступными навсегда",
      after.status_code == 200 and after.json()["usage"]["entities"].get("NAME") == 2,
      f"код={after.status_code}")


# --- ПОТОЛОК ИНСТАНСОВ: ОСВОБОЖДЁННЫЙ СЛОТ ОСТЫВАЕТ ----------------------
# Проверено руками до правки: на тарифе «Старт» (один контейнер) поднимались
# пять подряд — каждый освобождал свой слот сам и уступал место следующему.
print("\nПОТОЛОК ИНСТАНСОВ")
carousel_key = admin.post("/admin/issue", json={"org_id": "carousel", "plan": "start"},
                          headers=ADMIN).json()["key"]


def lease_as(key: str, instance: str, pubkey: str) -> int:
    return public.post("/v1/lease", json={
        "key": key, "instance_id": instance, "pubkey": pubkey,
        "engine_version": "1.0.0"}).status_code


def release_as(key: str, instance: str, pubkey: str) -> int:
    return public.post("/v1/release", json={
        "key": key, "instance_id": instance, "pubkey": pubkey}).status_code


served = []
for number in range(5):
    process = generate_process_key().public
    code = lease_as(carousel_key, f"c{number}", process)
    if code == 200:
        served.append(number)
        release_as(carousel_key, f"c{number}", process)
check("карусель контейнеров упирается в остывший слот", len(served) == 1,
      f"обслужено {len(served)} из 5 на тарифе в один инстанс")

# А ПЕРЕРАЗВЁРТЫВАНИЕ — ТОТ ЖЕ ТОМ, ТОТ ЖЕ `instance_id` — НЕ ЗАДЕТО ВОВСЕ.
# Это и есть причина, по которой остывание можно себе позволить.
redeploy = lease_as(carousel_key, "c0", generate_process_key().public)
check("переразвёртывание на том же томе поднимается сразу", redeploy == 200,
      f"POST /v1/lease -> {redeploy}")

refusal = public.post("/v1/lease", json={
    "key": carousel_key, "instance_id": "c9",
    "pubkey": generate_process_key().public, "engine_version": "1.0.0"}).json()
check("отказ называет работающий путь, а не только запрет",
      "ТОМ ЖЕ ТОМЕ" in refusal.get("detail", ""), refusal.get("detail", "")[:90])

budget_key = admin.post("/admin/issue", json={"org_id": "budget", "plan": "start"},
                        headers=ADMIN).json()["key"]
codes = []
for number in range(8):
    process = generate_process_key().public
    lease_as(budget_key, "b0", process)
    codes.append(release_as(budget_key, "b0", process))
check("бюджет освобождений исчерпывается и отвечает 429", 429 in codes,
      f"коды освобождений: {codes}")


# --- ОДНА ТОЧКА СПИСАНИЯ, И ОНА ЕСТЬ НА ОБОИХ ЛЕГАХ ----------------------
# Греп-проверяемый инвариант вместо памяти: `consume` забывали на прокси-леге
# дважды подряд — сначала счётчик запросов, потом ёмкость.
print("\nТОЧКА СПИСАНИЯ")
import pathlib  # noqa: E402

sources = {path.name: path.read_text(encoding="utf-8")
           for path in pathlib.Path("pseudex").glob("*.py")}
# `metering.py` содержит определение, а не вызов — его исключаем по имени.
billing_legs = {name for name, text in sources.items()
                if "metering.bill(" in text and name != "metering.py"}
stray = {name for name, text in sources.items()
         if ".consume(" in text and name not in ("metering.py", "license.py")}
check("оба лега списывают через одну функцию",
      billing_legs == {"service.py", "proxy.py"}, f"списывают: {sorted(billing_legs)}")
check("мимо неё ёмкость больше никто не трогает", not stray, f"мимо: {sorted(stray)}")


# --- ПРОТОКОЛ ЁМКОСТИ, НАСТОЯЩИМ КЛИЕНТОМ ПРОТИВ НАСТОЯЩЕГО СЕРВЕРА ------
# `TestClient` не даёт клиенту сетевого адреса, поэтому здесь поднимается
# настоящий uvicorn на петле: `LicenseClient` ходит по HTTP и никак иначе.
print("\nПРОТОКОЛ ЁМКОСТИ")
import threading  # noqa: E402

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from pseudex.bundle import BundleError  # noqa: E402
from pseudex.license import LicenseClient  # noqa: E402


def _free_port() -> int:
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


_port = _free_port()
_serving = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=_port,
                                         log_level="error"))
threading.Thread(target=_serving.run, daemon=True).start()
_base = f"http://127.0.0.1:{_port}"
for _ in range(200):
    try:
        httpx.get(f"{_base}/health", timeout=1)
        break
    except httpx.HTTPError:
        time.sleep(0.05)

os.environ["PSEUDEX_LICENSE_PUBKEY"] = server.PUBLIC_KEY


def engine(org: str, plan: str) -> LicenseClient:
    client = LicenseClient(
        base_url=_base, key=server.STORE.issue_key(org, plan), instance_id="i",
        ca_path="", usage_provider=lambda: {"requests": 0, "entities": {}, "values": 0})
    client.acquire()
    return client


# ЧЕСТНАЯ ЦЕПЬ — СЧЁТ РАВЕН РАСХОДУ. Это и есть обещание: не оценка сверху, а
# измерение, которое клиент может сверить со своим логом шлюза.
honest = engine("cap-honest", "start")
honest._meter_step()
for _ in range(honest._prefetch_at):
    honest.consume()
honest._meter_step()
served, _ = honest.capacity()
totals = server.STORE.billable("cap-honest")
check("честная цепь: к счёту ровно расход, а не потолок",
      totals["billable"] == served,
      f"расход {served}, к счёту {totals['billable']}, потолок {totals['granted']}")

# ПОВТОР УЖЕ ПРИНЯТОГО КВАНТА.
raw = httpx.post(f"{_base}/v1/meter", timeout=10, json={
    "key": honest._key, "instance_id": "i",
    "pubkey": honest._process_key.public, "nonce": "n"}).json()
honest._apply_quantum(raw, "n")
try:
    honest._apply_quantum(raw, "n")
    replayed = True
except BundleError:
    replayed = False
check("повтор принятого кванта не пополняет ёмкость", not replayed)

# ПОВТОР ЗАХВАЧЕННОЙ ЛИЗЫ: не даёт ёмкости И не обнуляет расход.
captured = httpx.post(f"{_base}/v1/lease", timeout=60, json={
    "key": honest._key, "instance_id": "i", "pubkey": honest._process_key.public,
    "engine_version": "1.0.0", "nonce": "CAPTURED"}).json()
before = honest.capacity()
try:
    honest._apply(captured)
    accepted = True
except BundleError:
    accepted = False
check("повтор лизы отвергнут и расход не обнулён",
      not accepted and honest.capacity() == before,
      f"ёмкость {before} -> {honest.capacity()}")

# БЛЭКХОЛ: ёмкость в STALE КОНЕЧНА и равна предоплаченному резерву.
blackhole = engine("cap-blackhole", "start")
blackhole._meter_step()
for _ in range(blackhole._prefetch_at):
    blackhole.consume()
blackhole._meter_step()
reserve = blackhole._reserve
blackhole._base_url = "http://127.0.0.1:1"
blackhole._last_ok_monotonic -= 10 ** 5
extra = 0
while blackhole.has_capacity() and extra < 10 ** 6:
    blackhole.consume()
    extra += 1
check("наш простой отдаёт ровно предоплаченный резерв и ни запросом больше",
      extra < 10 ** 6 and not blackhole.has_capacity(),
      f"обслужено в STALE {extra} при резерве {reserve}; раньше здесь был "
      f"безлимит на TTL+grace")

# МОЛЧАНИЕ НЕ ЗАНИЖАЕТ СЧЁТ: слепой шаг считает квант выбранным целиком.
silent = engine("cap-silent", "start")
silent._meter_step()
for _ in range(silent._prefetch_at):
    silent.consume()
spent, _ = silent.capacity()
# Так выглядит пропатченный клиент: ёмкость просит, расход не называет.
silent._report_secret = None
silent._meter_step()
silent._meter_step()
quiet = server.STORE.billable("cap-silent")
check("снятый отчёт не занижает счёт и виден числом",
      quiet["billable"] >= spent and quiet["unacked_quanta"] > 0,
      f"расход {spent}, к счёту {quiet['billable']}, "
      f"квантов без отчёта {quiet['unacked_quanta']}")

print(f"\nсломано {len(fails)}")
raise SystemExit(1 if fails else 0)
