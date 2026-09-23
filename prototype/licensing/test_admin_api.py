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

import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("PSEUDEX_LICENSE_DB", tempfile.mktemp(suffix=".db"))
os.environ["PSEUDEX_LICENSE_ADMIN_TOKEN"] = "test-admin"
os.environ["PSEUDEX_LICENSE_STOREFRONT_TOKEN"] = "test-shop"
sys.path.insert(0, ".")

# ЭТОТ НАБОР НЕ ЗАПУСКАЛСЯ В CI НИ РАЗУ С ТЕХ ПОР, КАК ТЮНИНГ СТАЛ ЗАПЕЧАТАННЫМ.
#
# Он поднимает НАСТОЯЩИЙ `LicenseClient` и берёт настоящую аренду; тюнинг едет
# в лизе (docs/tz-tuning-in-lease.md), никакого ключа настраивать не нужно.

from fastapi.testclient import TestClient  # noqa: E402

from licensing import server  # noqa: E402
from licensing.store import LicenseStore  # noqa: E402
from pseudex.bundle import generate_process_key, mac_report  # noqa: E402
# Что движок считает ОТВЕТОМ, а что нашим сбоем, — читается из самого движка,
# а не переписывается сюда строкой: копия жила бы своей жизнью ровно до первой
# правки в `pseudex/license.py`.
from pseudex.license import _ANSWER_CODES as _license_answer_codes  # noqa: E402

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
# мусорным циклом выше. Отказ там был бы работой допуска, а не дефектом.
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

# ПРОПУЩЕННЫЙ org_id — ОШИБКА, А НЕ ПРАВДОПОДОБНЫЙ НОЛЬ.
#
# `/admin/instances` рядом требует параметр, а `/admin/usage` не требовал:
# отсутствующий org_id запрашивался буквально пустой строкой и возвращал
# полностью оформленную структуру из нулей. Отличить её от настоящего клиента,
# который ещё не начал работать, нельзя ничем — а «этот клиент ничего не
# использовал» ровно то, в чём нельзя уверенно ошибаться на экране, по которому
# выставляют счёт. Вызывающий, потерявший параметр (опечатка в строке запроса
# консоли, незаданная переменная в скрипте), получал ответ вместо ошибки.
no_org = admin.get("/admin/usage", headers=ADMIN)
check("итоги без org_id отказывают, а не отдают ноль",
      no_org.status_code == 400,
      f"код={no_org.status_code} тело={no_org.text[:120]}")

# НЕИЗВЕСТНЫЙ ТАРИФ — 400, А НЕ ТИХОЕ ПОНИЖЕНИЕ ДО «СТАРТА».
#
# Дефолтом стояло `"standard"` — строка, которой нет ни в `PLAN_INSTANCES`, ни в
# `PLAN_GRANT`, ни в `QUANTUM_BOUNDS`, ни в `RESERVE_MAX`. Каждый lookup молча
# откатывался на «старт», поэтому ключ, выпущенный без явного тарифа, получал
# один контейнер и гранты по 5 000 запросов независимо от того, что купили. Ни
# отказа, ни строки в логе: клиент упирался в потолок инстансов чужого тарифа, и
# отказ называл предел, который ни один экран не мог объяснить.
unknown = admin.post("/admin/issue", json={"org_id": "u", "plan": "standard"},
                     headers=ADMIN)
check("неизвестный тариф отказывает при выпуске ключа",
      unknown.status_code == 400 and "known" in unknown.json(),
      f"код={unknown.status_code} тело={unknown.text[:160]}")

defaulted = admin.post("/admin/issue", json={"org_id": "d"}, headers=ADMIN)
check("тариф по умолчанию существует на самом деле",
      defaulted.status_code == 200
      and server.STORE.known_plan(server.STORE.lookup(defaulted.json()["key"]).plan),
      f"код={defaulted.status_code}")

# Сид кладёт ровно те тарифы, что объявлены константами, — ни больше ни меньше.
check("каждый объявленный тариф посеян в таблицу",
      set(server.STORE.known_plans()) == set(server.STORE.PLAN_INSTANCES),
      f"в таблице={server.STORE.known_plans()} "
      f"объявлено={sorted(server.STORE.PLAN_INSTANCES)}")

# ...и эта проверка обязана уметь падать. Сама по себе она истинна по построению
# цикла сидирования, поэтому смысл ей даёт следующая: тариф, объявленный НЕ ВО
# ВСЕХ таблицах, не должен доехать до базы с умолчаниями младшего тарифа.
class _HalfDeclaredStore(LicenseStore):
    PLAN_INSTANCES = dict(LicenseStore.PLAN_INSTANCES, gold=50)   # и больше нигде


try:
    _HalfDeclaredStore(tempfile.mktemp(suffix=".db"))
    seed_refused = ""
except ValueError as error:
    seed_refused = str(error)
check("неполный сид тарифов роняет старт, а не оседает умолчаниями",
      "gold" in seed_refused and "PLAN_GRANT" in seed_refused,
      seed_refused[:140] or "сид принял тариф, объявленный в одной таблице")


# --- ТАРИФ — СТРОКА, А НЕ КОНСТАНТА --------------------------------------
print("\nТАРИФ КАК ДАННЫЕ")

seeded = admin.get("/admin/plans", headers=ADMIN).json()["plans"]
check("посеянный тариф так и помечен",
      all(p["source"] == "seed" for p in seeded),
      f"источники={sorted({p['source'] for p in seeded})}")

edited = admin.post("/admin/plans",
                    json={"code": "work", "max_instances": 9, "actor": "ops:test"},
                    headers=SHOP)
check("витрина может править прайс-лист", edited.status_code == 200,
      f"код={edited.status_code}")
check("правка помечена и названа автором",
      edited.json()["plan"]["source"] == "edited"
      and edited.json()["plan"]["updated_by"] == "ops:test",
      f"строка={edited.json().get('plan')}")

# ГЛАВНОЕ СВОЙСТВО ТАБЛИЦЫ: правка переживает перезапуск процесса. Сид идёт
# `INSERT OR IGNORE` именно ради этого — `REPLACE` возвращал бы тариф к
# константе на каждом подъёме, и таблица была бы украшением.
reopened = LicenseStore(os.environ["PSEUDEX_LICENSE_DB"])
check("правка тарифа переживает переоткрытие базы",
      reopened.plan_row("work")["max_instances"] == 9,
      f"после переоткрытия={reopened.plan_row('work')['max_instances']}")
check("сид не затирает правку",
      reopened.plan_row("work")["source"] == "edited",
      f"источник={reopened.plan_row('work')['source']}")

# И тариф действительно РАБОТАЕТ по строке, а не по константе: потолок
# инстансов читается оттуда же, откуда его правили.
check("решение о потолке принимается по строке, а не по константе",
      server.STORE.instances_allowed("work") == 9
      and server.STORE.PLAN_INSTANCES["work"] == 4,
      f"строка={server.STORE.instances_allowed('work')} "
      f"константа={server.STORE.PLAN_INSTANCES['work']}")

# Мусор в теле не должен ни падать пятисоткой, ни ложиться на диск.
before_min = server.STORE.plan_row("work")["quantum_min"]
bad = [
    ({"code": "work", "max_instances": 5}, "без actor"),
    ({"code": "", "max_instances": 5, "actor": "x"}, "без code"),
    ({"code": "work", "max_instances": -1, "actor": "x"}, "отрицательное"),
    ({"code": "work", "max_instances": "много", "actor": "x"}, "не число"),
    ({"code": "work", "max_instances": 10 ** 12, "actor": "x"}, "за потолком"),
    ({"code": "work", "actor": "x"}, "нечего менять"),
    ({"code": "work", "quantum_min": 10 ** 6, "actor": "x"}, "пол выше потолка"),
]
refused = [why for body, why in bad
           if admin.post("/admin/plans", json=body, headers=ADMIN).status_code != 400]
check("мусор в правке тарифа отвергается, а не проходит", not refused,
      f"прошло={refused or 'ничего'}")
check("отвергнутая правка НЕ ложится на диск",
      server.STORE.plan_row("work")["quantum_min"] == before_min,
      f"было={before_min} стало={server.STORE.plan_row('work')['quantum_min']}")

# НОВЫЙ ТАРИФ ОБЯЗАН НАЗВАТЬ ВСЕ ПОЛЯ. Для неизвестного кода недостающие поля
# сливались с нулями, и `known_plan` такой тариф признавал: допуск считал
# `ceiling = allowed * 0 = 0` и отказывал клиенту в ПЕРВОЙ ЖЕ аренде, а нулевой
# `quantum_max` делал то же с ёмкостью. На паре 0/0 проверка «пол выше потолка»
# не срабатывает, а диапазонная проверка в ручке видит только присланные поля.
half = admin.post("/admin/plans",
                  json={"code": "gold", "max_instances": 4, "actor": "ops:test"},
                  headers=ADMIN)
check("новый тариф с половиной полей отвергается", half.status_code == 400,
      f"код={half.status_code} тело={half.text[:120]}")
check("отвергнутый новый тариф не появился в списке",
      "gold" not in server.STORE.known_plans(),
      f"известные={server.STORE.known_plans()}")
whole = admin.post("/admin/plans",
                   json={"code": "gold", "max_instances": 4,
                         "processes_per_instance": 16, "grant_size": 20000,
                         "quantum_min": 200, "quantum_max": 8000,
                         "reserve_max": 90000, "actor": "ops:test"},
                   headers=ADMIN)
check("новый тариф со всеми полями заводится и сразу работает",
      whole.status_code == 200 and server.STORE.instances_allowed("gold") == 4
      and server.STORE.processes_allowed("gold") == 16,
      f"код={whole.status_code} инстансов={server.STORE.instances_allowed('gold')}")


# --- ФЛОТ: ПАКЕТ ПО НАЗВАННЫМ, НЕ ПЕРЕЧИСЛЕНИЕ ---------------------------
# Витрина держит МЕНЬШИЙ токен и `/admin/list` ей не положен: каталог всех
# абонентов — единственное, что белый список защищает. Пакетная ручка обязана
# сохранять это свойство, то есть отдавать только то, что у неё спросили.
admin.post("/admin/issue", json={"org_id": "fleet-a", "plan": "start"}, headers=ADMIN)
admin.post("/admin/issue", json={"org_id": "fleet-b", "plan": "start"}, headers=ADMIN)
fleet = admin.get("/admin/fleet", params={"org_ids": "fleet-a,fleet-b,fleet-a"},
                  headers=SHOP)
returned = [row["org_id"] for row in fleet.json().get("orgs", [])]
check("флот отдаёт ровно названные организации, без повторов",
      fleet.status_code == 200 and returned == ["fleet-a", "fleet-b"],
      f"код={fleet.status_code} отдано={returned}")
check("флот не перечисляет абонентов сам",
      "v" not in returned and "carousel" not in returned,
      f"отдано={returned}")
check("флот без списка отказывает",
      admin.get("/admin/fleet", headers=ADMIN).status_code == 400)
check("флот с непомерным списком отказывает",
      admin.get("/admin/fleet",
                params={"org_ids": ",".join(str(i) for i in range(500))},
                headers=ADMIN).status_code == 400)
check("каталог всех абонентов витрине по-прежнему закрыт",
      admin.get("/admin/list", headers=SHOP).status_code == 403
      and admin.get("/admin/list", headers=ADMIN).status_code == 200)

# Одна строка на ОРГАНИЗАЦИЮ, а не на ключ: сторож печатает `late[:20]`, и
# клиент с тремя ключами занимал в этом списке три места из двадцати.
admin.post("/admin/issue", json={"org_id": "fleet-a", "plan": "start"}, headers=ADMIN)
admin.post("/admin/issue", json={"org_id": "fleet-a", "plan": "start"}, headers=ADMIN)
catalogue = admin.get("/admin/list", headers=ADMIN).json()["orgs"]
rows_for_a = [row for row in catalogue if row["org_id"] == "fleet-a"]
check("каталог даёт одну строку на организацию, а не на ключ",
      len(rows_for_a) == 1 and rows_for_a[0]["keys"] == 3,
      f"строк={len(rows_for_a)} ключей={rows_for_a[0]['keys'] if rows_for_a else '?'}")
check("сторож по-прежнему находит поля, которые читает",
      all(field in rows_for_a[0] for field in ("org_id", "last_lease")),
      f"поля={sorted(rows_for_a[0])}")

# ОТЗЫВ ОДНОГО КЛЮЧА НЕ ДЕЛАЕТ ОРГАНИЗАЦИЮ ОТОЗВАННОЙ. `set_status` двигает все
# ключи разом, а `revoke_key_hash` — ровно один: им и отзывают утёкший ключ, не
# останавливая клиента. Статус свежайшего ключа показал бы организацию
# отозванной именно потому, что отозвали последний выпущенный.
leaked = admin.post("/admin/issue", json={"org_id": "fleet-a", "plan": "start"},
                    headers=ADMIN).json()["key"]
admin.post("/admin/revoke_key",
           json={"key_hash": __import__("hashlib").sha256(leaked.encode()).hexdigest()},
           headers=ADMIN)
after_revoke = [row for row in admin.get("/admin/list", headers=ADMIN).json()["orgs"]
                if row["org_id"] == "fleet-a"][0]
check("отзыв одного ключа не отзывает организацию",
      after_revoke["status"] == "active" and after_revoke["active_keys"] == 3,
      f"статус={after_revoke['status']} активных={after_revoke['active_keys']}")
check("раскладка по статусам видна, а не додумывается",
      after_revoke["statuses"].get("revoked") == 1,
      f"раскладка={after_revoke['statuses']}")


# --- СУТОЧНЫЕ СРЕЗЫ ------------------------------------------------------
# Без них график «по дням» рисовать не из чего: `usage` хранит ОДИН
# перезаписываемый снимок на инстанс (docs/tz-site.md §6).
server.STORE.record_usage("hist", "i1", 100, {}, 10, seq=1, prev="",
                          signature="s1", trust="signed", report_pubkey="hk1")
server.STORE.record_usage("hist", "i2", 40, {}, 4, seq=1, prev="",
                          signature="s2", trust="signed", report_pubkey="hk2")
history = server.STORE.usage_history("hist")
check("срез суммирует инстансы организации внутри суток",
      len(history) == 1 and history[-1]["requests"] == 140,
      f"история={history}")

# Неподтверждённое не входит в счёт — значит и в график счёта не входит,
# иначе экран показывал бы объём, за который никто не выставит.
server.STORE.record_usage("hist", "i1", 10 ** 6, {}, 10 ** 6, trust="unsigned",
                          report_pubkey="hk1")
check("неподписанный отчёт не попадает в график",
      server.STORE.usage_history("hist")[-1]["requests"] == 140,
      f"после неподписанного={server.STORE.usage_history('hist')[-1]['requests']}")

# Повтор старого честного отчёта имеет настоящий MAC и проходит проверку
# подписи; `record_usage` защищает от него `requests` максимумом, и срез обязан
# вести себя так же, иначе график поедет вниз там, где счёт не поехал.
server.STORE.record_usage("hist", "i1", 100, {}, 10, seq=1, prev="",
                          signature="s1", trust="signed", report_pubkey="hk1")
check("повтор старого отчёта не опускает график",
      server.STORE.usage_history("hist")[-1]["requests"] == 140,
      f"после повтора={server.STORE.usage_history('hist')[-1]['requests']}")

# МОЛЧАВШИЙ ИНСТАНС ПЕРЕНОСИТСЯ ВПЕРЁД, А НЕ ИСЧЕЗАЕТ. Ряд обязан быть
# монотонным: сумма только по отчитавшимся сегодня инстансам даёт падение там,
# где ничего не упало, разность соседних суток становится отрицательной, а
# последняя точка расходится с `usage_totals`, который суммирует все инстансы.
# Вчерашние сутки подделываются прямо в таблице — календарь не подвинуть.
with server.STORE._lock:
    server.STORE._conn.execute(
        "UPDATE usage_daily SET day='2000-01-01' WHERE org_id='hist' AND instance_id='i2'")
    server.STORE._conn.commit()
carried = server.STORE.usage_history("hist")
check("молчащий инстанс переносится вперёд, а ряд остаётся монотонным",
      len(carried) == 2 and carried[0]["requests"] == 40
      and carried[-1]["requests"] == 140
      and all(carried[i]["requests"] <= carried[i + 1]["requests"]
              for i in range(len(carried) - 1)),
      f"ряд={[(row['day'], row['requests']) for row in carried]}")
check("последняя точка графика сходится с итогами",
      carried[-1]["requests"] == server.STORE.usage_totals("hist")["requests"],
      f"график={carried[-1]['requests']} "
      f"итоги={server.STORE.usage_totals('hist')['requests']}")

chains = admin.get("/admin/chains", params={"org_id": "hist"}, headers=SHOP)
check("детализация цепи называет процессы, а не только сумму",
      chains.status_code == 200 and len(chains.json()["processes"]) == 2,
      f"код={chains.status_code} процессов={len(chains.json().get('processes', []))}")
# Перечисление ограничено, как и всякое другое: `process_reports` получает
# строку на каждый воркер на каждый перезапуск и не чистится ничем.
capped = server.STORE.chain_detail("hist", limit=1)
check("детализация цепи ограничена, но сумма считается по всем",
      len(capped["processes"]) == 1 and capped["processes_total"] == 2,
      f"показано={len(capped['processes'])} всего={capped['processes_total']}")
check("ключ процесса в детализации урезан до префикса",
      all(len(p["pubkey"]) <= 16 for p in chains.json()["processes"]),
      f"длины={[len(p['pubkey']) for p in chains.json()['processes']]}")
check("детализация цепи без org_id отказывает",
      admin.get("/admin/chains", headers=ADMIN).status_code == 400)


# --- СЛОТЫ, ПОКОЛЕНИЯ, ФЕНСИНГ — ЧЕРЕЗ HTTP, ПРОТИВ НАСТОЯЩЕГО СЕРВЕРА ---
#
# ВСЁ, ЧТО СТОЯЛО ЗДЕСЬ РАНЬШЕ, УДАЛЕНО ВМЕСТЕ С МЕХАНИЗМАМИ, КОТОРЫЕ ОНО
# ПИНИЛО, и каждое удаление названо тем дефектом, который оно лечило:
#
#   «карусель контейнеров упирается в бюджет перевыдач» — бюджет лечил
#     Б26bis/ter (единственный ограничитель темпа карусели). Свойство УТРАТИЛО
#     СИЛУ: карусель — это поколения на ОДНОМ слоте, из которых покупает ровно
#     одно, умножения нет, ограничивать темп нечего. Остаток кольца бюджет и не
#     ограничивал никогда («молчащее кольцо не ограничено»), и его величина
#     печатается ниже числом.
#   «замолчавший 20 мин контейнер отдаёт слот новому», «про движок без пульса
#     сказано честно», «кабинет показывает труп silent» — лечили Б26 (труп
#     держал слот до суток). ЛЕЧИТСЯ ТЕПЕРЬ: занятость не решается вовсе;
#     вернувшаяся установка забирает свой слот по свидетельству личности,
#     чужая — по ранжированию. Держится проверками «десять перезапусков» и
#     «раскатка» ниже.
#   «эхо ухода посчитано ПО КЛЮЧАМ», «а ушедший и продолжающий покупать
#     ёмкость слота не отдаёт» — лечили Б26sexies (кольцо покупало ёмкость
#     отпущенными ключами). ЛЕЧИТСЯ: покупка мимо текущего эпоха невозможна.
#   «продление отобранного ключа — 409 instance_limit» — лечило Б26ter
#     (отобранный ключ продлевался вечно). Свойство УТРАТИЛО СИЛУ: отбирать
#     нечего, на аренде отказов нет; эквивалент — «отфенсенный не покупает».
#   «потолок мест рабочих процессов отказывает и называет срок» — лечило
#     Б26quater. Свойство УТРАТИЛО СИЛУ: мест нет.
print("\nСЛОТЫ И ПОКОЛЕНИЯ")


def issue(org: str, plan: str = "start") -> str:
    return admin.post("/admin/issue", json={"org_id": org, "plan": plan},
                      headers=ADMIN).json()["key"]


def lease_as(key: str, start: str, instance: str, pubkey: str,
             version: str = "0.3.18", nonce: str = "n"):
    body = {"key": key, "instance_id": instance, "pubkey": pubkey,
            "engine_version": version, "nonce": nonce + pubkey[:8]}
    if start is not None:
        body["start_id"] = start
    return public.post("/v1/lease", json=body)


def meter_as(key: str, pubkey: str, consumed: int | None = None,
             slot_no: int | None = None, epoch: int | None = None):
    # ОДИН КВАНТ В СЕКУНДУ НА КЛЮЧ (`MIN_METER_INTERVAL_SECONDS`) — это НАША
    # полоса, а не потолок тарифа, и честный движок приходит раз в четыре
    # минуты. Мерить сквозь неё значило бы мерить лимит частоты вместо
    # фенсинга, поэтому проверка её пережидает, а не отключает.
    body: dict = {"key": key, "pubkey": pubkey, "nonce": "m" + pubkey[:8]}
    if consumed is not None or slot_no is not None:
        ack: dict = {"consumed": consumed or 0}
        if slot_no is not None:
            ack["slot_no"] = slot_no
        if epoch is not None:
            ack["epoch"] = epoch
        body["ack"] = ack
    answer = public.post("/v1/meter", json=body)
    if answer.status_code == 429:
        time.sleep(1.05)
        answer = public.post("/v1/meter", json=body)
    return answer


def release_as(key: str, instance: str, pubkey: str) -> int:
    return public.post("/v1/release", json={
        "key": key, "instance_id": instance, "pubkey": pubkey}).status_code


def slots_of(org: str) -> dict:
    return admin.get(f"/admin/instances?org_id={org}", headers=ADMIN).json()


def new_key() -> str:
    return generate_process_key().public


# ── S-01. ОБЫЧНЫЙ СТАРТ: N ВОРКЕРОВ ОДНОГО СТАРТА — ОДНО ПОКОЛЕНИЕ ──────────
# Если бы воркеры считались поколениями, контейнер на тарифе «Старт» фенсил бы
# сам себя и был бы сломан по построению. Поэтому `PSEUDEX_START_ID` чеканится
# один раз до фан-аута, а сервер обязан прочесть N аренд как один старт.
normal = issue("normal")
codes = [lease_as(normal, "S1", "vol-one", new_key()).json() for _ in range(6)]
view = slots_of("normal")
holder = view["slots"][0]["holder"]
check("шесть воркеров одного старта — один слот, один эпох",
      {(row["slot_no"], row["epoch"]) for row in codes} == {(1, 1)},
      f"{sorted({(r['slot_no'], r['epoch']) for r in codes})}")
check("и это ОДНО поколение, а не шесть", view["generations_24h"] == 1,
      f"поколений за сутки {view['generations_24h']}")
check("занято — число сервера, воркеры — отдельное число",
      view["occupied"] == 1 and holder["workers_heard"] == 6,
      f"занято {view['occupied']}, воркеров {holder['workers_heard']}")

# ── S-02. ДЕСЯТЬ ПЕРЕЗАПУСКОВ ПОДРЯД ────────────────────────────────────────
# ЧИСЛО ИЗ Б26sexies СТОИТ В ТЕКСТЕ ПРОВЕРКИ КАК БАЗА: выпущенный 0.3.17 на
# этом же сценарии отказывал на 6-м, 9-м и 3-м честном старте. Десять — потому
# что «работает дважды» здесь и было дефектом.
restart = issue("restart")
restarts = [lease_as(restart, f"R{n}", "vol-one", new_key()) for n in range(10)]
view = slots_of("restart")
check("десять перезапусков подряд — ни одного отказа (0.3.17 отказывал на 6/9/3)",
      all(r.status_code == 200 for r in restarts),
      f"коды {[r.status_code for r in restarts]}")
check("и это десять поколений на ОДНОМ слоте, эпох 10",
      view["slot_count"] == 1 and view["slots"][0]["epoch"] == 10
      and view["generations_24h"] == 10,
      f"слотов {view['slot_count']}, эпох {view['slots'][0]['epoch']}")

# ── S-03. OOM-КИЛЛ == ПЕРЕЗАПУСК, БАЙТ В БАЙТ ──────────────────────────────
# Один код с флагом «звать release или нет»; записи сервера обязаны различаться
# ТОЛЬКО тем, что решения не читают. Пара, потому что по отдельности каждая
# половина зелёная при сломанной второй.
def two_restarts(org: str, say_goodbye: bool) -> dict:
    key = issue(org)
    first = new_key()
    lease_as(key, "G1", "vol-one", first)
    if say_goodbye:
        release_as(key, "vol-one", first)
    lease_as(key, "G2", "vol-one", new_key())
    return slots_of(org)


polite, killed = two_restarts("polite", True), two_restarts("killed", False)


def decisive(view: dict) -> dict:
    slot = view["slots"][0]
    return {"epoch": slot["epoch"], "occupied": view["occupied"],
            "installation": slot["holder"]["installation_id"],
            "start_id": slot["holder"]["start_id"],
            "generations": view["generations_24h"]}


check("OOM и docker stop дают одинаковые записи во всём, что читает решение",
      decisive(polite) == decisive(killed),
      f"{decisive(polite)} vs {decisive(killed)}")
check("и разница есть только в том, что решений не читает (released)",
      polite["slots"][0]["holder"]["released"] is False
      and killed["slots"][0]["holder"]["released"] is False,
      "обе записи — про НОВОЕ поколение, прощание записано у предыдущего")

# ── S-04. ПЕРЕКАТНОЕ ОБНОВЛЕНИЕ: ДВА ЖИВЫХ, ПОКУПАЕТ ОДИН ──────────────────
# K8s удваивает однорепличный Deployment по умолчанию, поэтому два живых
# контейнера на тарифе в один — штатно, при КАЖДОМ обновлении.
rollout = issue("rollout")
old_key, new_pod = new_key(), new_key()
lease_as(rollout, "OLD", "vol-one", old_key)
before = meter_as(rollout, old_key)
lease_as(rollout, "NEW", "vol-one", new_pod)
fenced = meter_as(rollout, old_key)
fresh = meter_as(rollout, new_pod)
check("на аренде раскатки ни одного 409", fresh.status_code == 200,
      f"новый под -> {fresh.status_code}")
check("старый под отфенсен на ПОКУПКЕ, а не на аренде",
      before.status_code == 200 and fenced.status_code == 409
      and fenced.json().get("error") == "fenced",
      f"до {before.status_code}, после {fenced.status_code} "
      f"{fenced.json().get('error')}")
check("отказ называет ЧТО произошло и не советует останавливать несуществующее",
      "занял более новый запуск" in fenced.json().get("detail", "")
      and "лишний" not in fenced.json().get("detail", "").lower(),
      fenced.json().get("detail", "")[:100])
check("и несёт свой эпох, текущий и держателя — чтобы клиент мог это показать",
      {"slot_no", "epoch", "current_epoch", "holder_start_id", "holder_since"}
      <= set(fenced.json()),
      f"{sorted(fenced.json())}")

# ── S-16. ФОРМА ОТКАЗА — ЭТО ТРЕБОВАНИЕ К ВЫПУЩЕННОМУ ФЛОТУ (Б30) ──────────
# Здесь стоял `instance_limit`, и комментарий сервера обещал, что «процесс
# доживает на уже купленном кванте». Выпущенный движок делал обратное:
# `instance_limit ∈ _ANSWER_CODES` → `_terminal_code` → `_expire()` → бандл
# выгружен, `/mask` 503 в ту же секунду, оплаченный остаток сгорел.
check("код отказа ВНЕ _ANSWER_CODES выпущенных движков — иначе флот гаснет, а не доцеживает",
      "fenced" not in _license_answer_codes,
      f"_ANSWER_CODES={sorted(_license_answer_codes)}")
check("и едет как 409, который движок держит за временный сбой",
      fenced.status_code == 409,
      "неизвестный статус вне _GRACE_WORTHY_STATUS движок читает как LicenseError")
import pathlib as _pathlib  # noqa: E402

_server_source = _pathlib.Path("licensing/server.py").read_text(encoding="utf-8")
_meter_block = _server_source[_server_source.index('@app.post("/v1/meter")'):
                              _server_source.index('@app.post("/v1/usage")')]
check("`/v1/meter` не выдаёт instance_limit ни на одном пути",
      '"instance_limit"' not in _meter_block,
      "греп по телу ручки + прогон выше")

# ── S-09. ВСЁ, ЧТО МЫ ЗНАЕМ, — НАША ЗАПИСЬ ─────────────────────────────────
# Клиент называет `instance_id` и `start_id` сам, поэтому он выбирает, КАКОЙ
# слот занять; завести слот, понизить эпох или купить мимо текущего эпоха он не
# может ничем.
ours = issue("ours")
mine = new_key()
claim = lease_as(ours, "O1", "vol-one", mine).json()
# ПЕРВЫЙ КВАНТ ПОКУПАЕТСЯ ЧЕСТНО, И ТОЛЬКО ПОТОМ ВРЁТ ТЕГ. Первый квант
# процесса продаётся всегда, даже отфенсенному (иначе выпущенный движок,
# покупающий его внутри `acquire()`, не поднялся бы вовсе), — значит соврать
# в него нельзя и проверять на нём фенсинг бессмысленно.
meter_as(ours, mine, consumed=0, slot_no=claim["slot_no"], epoch=claim["epoch"])
liar = meter_as(ours, mine, consumed=5, slot_no=claim["slot_no"],
                epoch=claim["epoch"] + 5)
check("эпох в ack НОВЕЕ текущего — это не «ещё новее», это fenced",
      liar.status_code == 409 and liar.json().get("error") == "fenced",
      f"{liar.status_code} {liar.json().get('error')}")
wrong_slot = meter_as(ours, mine, consumed=5, slot_no=claim["slot_no"] + 1,
                      epoch=claim["epoch"])
check("чужой slot_no в ack — тоже fenced, а не выдача по чужому тегу",
      wrong_slot.status_code == 409, f"{wrong_slot.status_code}")
honest = meter_as(ours, mine, consumed=5, slot_no=claim["slot_no"],
                  epoch=claim["epoch"])
check("а сошедшийся тег покупает как обычно", honest.status_code == 200,
      f"{honest.status_code}")
check("слотов ровно столько, сколько по тарифу — назвать лишний нечем",
      len(slots_of("ours")["slots"]) == slots_of("ours")["slot_count"] == 1)

# ── S-10. ГОНКА: СТО ОДНОВРЕМЕННЫХ АРЕНД ОДНОГО СТАРТА ─────────────────────
# Между отдельным решением и отдельной записью лок отпускался, и замер прошлого
# захода дал 71 гонку из 100, прошедшую потолок. Здесь чеканится ЭПОХ, и сто
# воркеров одного старта обязаны получить один.
import threading as _threading  # noqa: E402

race_key = issue("race")
race_results: list[int] = []
race_lock = _threading.Lock()
barrier = _threading.Barrier(50)


def _race(number: int) -> None:
    barrier.wait()
    got = lease_as(race_key, "RACE", "vol-one", new_key()).json()
    with race_lock:
        race_results.append(got.get("epoch", -1))


threads = [_threading.Thread(target=_race, args=(n,)) for n in range(50)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
check("пятьдесят одновременных аренд одного старта — ровно один эпох",
      set(race_results) == {1}, f"эпохи {sorted(set(race_results))}")

# ── S-06. КОЛЬЦО: ОСТАТОК ПЕЧАТАЕТСЯ ЧИСЛОМ, А НЕ ОБЪЯВЛЯЕТСЯ ЗАКРЫТЫМ ─────
# Конструкция делает обороты ВИДИМЫМИ и не делает их дороже: полоса на аренду —
# `Q_min` тарифа, ровно как сегодня. Число печатается здесь, чтобы никто не
# назвал этот класс закрытым (§8.1).
ring = issue("ring")
TURNS = 8
for turn in range(TURNS):
    process = new_key()
    lease_as(ring, f"T{turn}", "vol-one", process)
    meter_as(ring, process)
    release_as(ring, "vol-one", process)
view = slots_of("ring")
usage = admin.get("/admin/usage?org_id=ring", headers=ADMIN).json().get("usage", {})
granted = int(usage.get("capacity_granted", 0))
check("кольцо видно ПОИМЁННО: эпох = числу оборотов, все без подтверждения",
      view["slots"][0]["epoch"] == TURNS and view["generations_24h"] == TURNS
      and view["epochs_unacked_24h"] == TURNS,
      f"эпох {view['slots'][0]['epoch']}, без ack {view['epochs_unacked_24h']}")
check(f"ОСТАТОК, НАЗВАННЫЙ ЧИСЛОМ: {granted} выданной ёмкости при нуле к начислению",
      granted == 200 * TURNS and int(usage.get("capacity_billable", 0)) == 0,
      f"granted={granted}, billable={usage.get('capacity_billable')} — "
      f"это те же 200 за оборот, что и до слотов; закрывает договор, не техника")
anomalies = admin.get("/admin/anomalies", headers=ADMIN).json().get("anomalies", [])
ring_row = next((row for row in anomalies if row["org_id"] == "ring"), None)
check("и организация попадает в аномалии с причиной про поколения без расхода",
      ring_row is not None and ring_row["epochs_unacked"] == TURNS
      and any("acknowledged nothing" in reason for reason in ring_row["reasons"]),
      f"{ring_row['reasons'] if ring_row else 'её нет в отчёте'}")

# ── S-07. КЛОН ТОМА: ДВА СТАРТА ОДНОЙ УСТАНОВКИ ЧЕРЕДУЮТСЯ НА ОДНОМ СЛОТЕ ──
clone = issue("clone")
first_key, second_key = new_key(), new_key()
lease_as(clone, "C1", "vol-one", first_key)
meter_as(clone, first_key)
lease_as(clone, "C2", "vol-one", second_key)          # клон на второй машине
meter_as(clone, second_key)                           # его первый квант — внутри acquire()
first_fenced = meter_as(clone, first_key)
lease_as(clone, "C1", "vol-one", first_key)           # перезаявка первого
second_fenced = meter_as(clone, second_key)
view = slots_of("clone")
check("клон тома делит ОДИН слот, а не заводит второй инстанс",
      view["slot_count"] == 1 and view["occupied"] == 1,
      f"{view['occupied']} из {view['slot_count']}")
check("и каждый покупает только пока держит: чередование, а не удвоение",
      first_fenced.status_code == 409 and second_fenced.status_code == 409,
      f"{first_fenced.status_code}/{second_fenced.status_code}")
check("перезаявки видны числом — это вход аномалии slot_contention",
      view["slot_contention_24h"] >= 1, f"{view['slot_contention_24h']}")

# ── S-08. РОСТ С 2 ДО 20 ВОРКЕРОВ (E8 ИСЧЕЗАЕТ КАК КЛАСС) ─────────────────
# E8: шестнадцать воркеров упирались в потолок МЕСТ на третьем перезапуске.
# Мест нет — нечему кончаться.
wide = issue("wide")
first_wave = [lease_as(wide, "W1", "vol-one", new_key()) for _ in range(20)]
second_wave = [lease_as(wide, "W2", "vol-one", new_key()) for _ in range(20)]
view = slots_of("wide")
check("двадцать воркеров и перезапуск на двадцать новых — ни одного отказа",
      all(r.status_code == 200 for r in first_wave + second_wave),
      f"отказов {sum(1 for r in first_wave + second_wave if r.status_code != 200)}")
check("и старые двадцать ключей не считаются нигде",
      view["slots"][0]["holder"]["workers_heard"] == 20
      and view["slots"][0]["epoch"] == 2,
      f"воркеров {view['slots'][0]['holder']['workers_heard']}")
check("processes_per_instance — строка тарифа для экрана, не замок",
      view["processes_per_instance"] == 32,
      "печатается как «тариф рассчитан на 32», решений не принимает")

# ── S-05. ОБРЫВ СЕТИ НА 72 Ч (§4.5) ────────────────────────────────────────
# ЭТОТ СЦЕНАРИЙ — ЕДИНСТВЕННЫЙ, ГДЕ КЛИЕНТ НЕ ДЕЛАЕТ РОВНО НИЧЕГО, и проверять
# «сервер не принял решения по молчанию» через «ничего не произошло» нельзя:
# такая проверка не может упасть, а значит ничего не держит (§9). Поэтому
# молчание здесь ЗАПУСКАЕТ ту работу, которая по молчанию и судила в шести
# прошлых заходах, — окно аренды истекает, и по таблицам проходит чистка. Слот
# обязан пережить и то и другое.
outage = issue("outage")
out_key = new_key()
lease_as(outage, "O1", "vol-one", out_key)
meter_as(outage, out_key)
before_outage = slots_of("outage")["slots"][0]

# 72 часа: аренда вышла из окна, отметку слота не двигали трое суток.
_gone = time.time() - 72 * 3600
server.STORE._conn.execute("UPDATE leases SET issued_at=? WHERE org_id=?",
                           (_gone, "outage"))
server.STORE._conn.execute("UPDATE generations SET last_lease_at=? WHERE org_id=?",
                           (_gone, "outage"))
server.STORE._conn.execute("UPDATE slots SET last_heard_at=? WHERE org_id=?",
                           (_gone, "outage"))
server.STORE._conn.commit()
server.STORE.prune_leases(86400)

after_outage = slots_of("outage")["slots"][0]
check("трое суток молчания не двигают ни эпох, ни держателя — по молчанию "
      "сервер не решает ничего",
      after_outage["epoch"] == before_outage["epoch"]
      and after_outage["holder"] is not None
      and after_outage["holder"]["start_id"] == "O1",
      f"эпох {before_outage['epoch']} -> {after_outage['epoch']}, "
      f"держатель {after_outage['holder'] and after_outage['holder']['start_id']}")

# ВОЗВРАТ. Аренда та же, поколение своё — эпох НЕ поднимается: это продление, а
# не перезаявка. Краснеет, если чистка забрала строку поколения держателя.
back = lease_as(outage, "O1", "vol-one", out_key, nonce="back")
_back_view = slots_of("outage")
check("возврат после обрыва — тот же эпох и ни одного отказа",
      back.status_code == 200
      and back.json()["epoch"] == before_outage["epoch"]
      and _back_view["generations_24h"] == 1,
      f"{back.status_code} эпох {back.json().get('epoch')} "
      f"поколений {_back_view['generations_24h']}")
check("и покупки возобновились с первого же кванта",
      meter_as(outage, out_key).status_code == 200,
      "иначе обрыв стоил бы клиенту слота, которого у него никто не забирал")

# ЗАМЕНА НА НОВОМ ТОМЕ ВО ВРЕМЯ ОБРЫВА. Тариф в один слот, свободных нет —
# ранжирование отдаёт слот тому, кого слышали раньше всех, то есть молчащему
# O1. Вернувшийся O1 получает 409 на ПОКУПКЕ и 200 на аренде, перезаявляет и
# забирает слот назад: два живых контейнера чередуются (§3bis.3), и ни один не
# заперт. Краснеет при возврате порога «молчит дольше T» в любую из сторон.
swap = issue("swap")
old_vol, new_vol = new_key(), new_key()
lease_as(swap, "SW-OLD", "vol-old", old_vol)
meter_as(swap, old_vol)
server.STORE._conn.execute("UPDATE slots SET last_heard_at=? WHERE org_id=?",
                           (time.time() - 72 * 3600, "swap"))
server.STORE._conn.commit()
replacement = lease_as(swap, "SW-NEW", "vol-new", new_vol)
check("замена на НОВОМ томе во время обрыва получает слот арендой, а не отказом",
      replacement.status_code == 200 and replacement.json()["slot_no"] == 1
      and replacement.json()["epoch"] == 2,
      f"{replacement.status_code} слот {replacement.json().get('slot_no')} "
      f"эпох {replacement.json().get('epoch')}")
returned = meter_as(swap, old_vol)
check("а вернувшийся из обрыва узнаёт об этом на ПОКУПКЕ, доцеживая купленное",
      returned.status_code == 409 and returned.json()["error"] == "fenced",
      f"{returned.status_code} {returned.json().get('error')}")
reclaim = lease_as(swap, "SW-OLD", "vol-old", old_vol)
swap_view = slots_of("swap")
check("его перезаявка возвращает слот — ни один из двух не заперт",
      reclaim.status_code == 200 and reclaim.json()["epoch"] == 3
      and swap_view["slots"][0]["holder"]["start_id"] == "SW-OLD",
      f"эпох {reclaim.json().get('epoch')}, держатель "
      f"{swap_view['slots'][0]['holder']['start_id']}")
check("а чередование названо числом, а не спрятано",
      swap_view["slot_contention_24h"] >= 1,
      f"slot_contention_24h {swap_view['slot_contention_24h']}")

# ── S-11. ПРОКСИ И САЙДКАР — ОДНА ЛИЧНОСТЬ, ОДНИ ЗАПИСИ (§4.9) ─────────────
# Слой лицензии не знает, какое плечо его вызвало, и проверяется это ДВАЖДЫ,
# потому что разойтись эти два плеча уже успевали: `proxy.py` держал случайный
# `instance_id`, пока сайдкар брал его из тома, и один `docker restart` запирал
# клиента на сутки. Одинаковость конструкции — мехническая половина; вторая
# половина в том, что сервер не читает из тела аренды ничего, чем плечи
# отличаются.
import ast as _ast


def _license_kwargs(path: str) -> dict[str, str]:
    tree = _ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in _ast.walk(tree):
        if (isinstance(node, _ast.Call) and isinstance(node.func, _ast.Name)
                and node.func.id == "LicenseClient"):
            return {kw.arg or "": _ast.unparse(kw.value) for kw in node.keywords}
    return {}


_proxy_kwargs = _license_kwargs("pseudex/proxy.py")
_service_kwargs = _license_kwargs("pseudex/service.py")
_differ = sorted(name for name in set(_proxy_kwargs) | set(_service_kwargs)
                 if _proxy_kwargs.get(name) != _service_kwargs.get(name))
check("оба плеча собирают клиента лицензии ОДНИМ И ТЕМ ЖЕ выражением",
      bool(_proxy_kwargs) and _proxy_kwargs == _service_kwargs,
      f"расходятся: {_differ}" if _differ else
      f"{len(_proxy_kwargs)} аргументов, включая instance_id и usage_provider")

# И СЛОЙ ЛИЦЕНЗИИ НЕ ЗНАЕТ НИ ОДНОГО ПОНЯТИЯ ПЛЕЧА. `conversation_id` — область
# ПОДМЕН (волт); попади оно сюда, слот стал бы функцией трафика.
_license_source = Path("pseudex/license.py").read_text(encoding="utf-8")
check("и не знает ни одного понятия шлюза — слот не функция трафика",
      "conversation_id" not in _license_source and "org_id" not in _license_source,
      "иначе одно плечо заводило бы поколения там, где другое продлевает")

# ПОВЕДЕНЧЕСКАЯ ПОЛОВИНА: одна последовательность событий, разные плечи.
# Отличие плеч в теле аренды не существует, и это проверяется тем, что сервер
# на лишние поля не реагирует ни одной записью.
legs = {}
for leg, extra in (("sidecar", {}),
                   ("proxy", {"conversation_id": "c-1", "org_id": "ignored"})):
    org = f"leg-{leg}"
    leg_key, leg_pub = issue(org), new_key()
    body = {"key": leg_key, "instance_id": "vol-one", "pubkey": leg_pub,
            "engine_version": "0.3.18", "nonce": "leg" + leg_pub[:8],
            "start_id": "LEG", **extra}
    public.post("/v1/lease", json=body)
    meter_as(leg_key, leg_pub)
    view = slots_of(org)
    row = server.STORE._fetchone(
        "SELECT slot_no, epoch FROM meter WHERE org_id=?", (org,))
    legs[leg] = {"epoch": view["slots"][0]["epoch"], "occupied": view["occupied"],
                 "generations": view["generations_24h"],
                 "start_id": view["slots"][0]["holder"]["start_id"],
                 "meter_tag": (int(row[0] or 0), int(row[1] or 0))}
check("одна последовательность событий даёт одинаковые записи с обоих плеч",
      legs["sidecar"] == legs["proxy"],
      f"{legs['sidecar']} vs {legs['proxy']}")

# ── ПОРЯДОК ПРЕДПОЧТЕНИЯ СЛОТОВ: СВОЙ РАНЬШЕ СВОБОДНОГО ───────────────────
# ОТСТУПЛЕНИЕ ОТ БУКВЫ §3.2 ТЗ, И ВОТ ЧЕМ ОНО КУПЛЕНО. Там порядок a→b→c:
# свободный слот, потом СВОЙ (та же установка), потом ранжирование. На тарифе
# в один слот оба порядка совпадают — свободных не бывает, — и все девять
# сценариев ТЗ написаны на нём. На тарифе с запасом буква давала экран, который
# врёт: ОДИН контейнер, перезапущенный трижды, занимал три слота (каждый старт
# брал очередной свободный, прежний оставался за мёртвым поколением), и кабинет
# печатал «занято 3 из 3» клиенту с одним работающим контейнером — то есть
# продавал апгрейд, которого не нужно. Это класс Б26bis дословно.
#
# Проверка краснеет при возврате буквы: `walked` станет [1, 2, 3].
roomy_plan = "industrial"
roomy = issue("roomy", roomy_plan)
walked = [lease_as(roomy, f"K{n}", "vol-one", new_key()).json()["slot_no"]
          for n in range(3)]
roomy_view = slots_of("roomy")
check("перезапуск ТОЙ ЖЕ установки возвращается на СВОЙ слот, а не берёт новый",
      walked == [1, 1, 1], f"слоты {walked}")
check("и занятость остаётся одна — столько контейнеров у клиента и есть",
      roomy_view["occupied"] == 1 and roomy_view["slots"][0]["epoch"] == 3,
      f"занято {roomy_view['occupied']} из {roomy_view['slot_count']}, "
      f"поколение {roomy_view['slots'][0]['epoch']}")
# А ЧУЖАЯ УСТАНОВКА ПРИ СВОБОДНЫХ СЛОТАХ БЕРЁТ СВОБОДНЫЙ, А НЕ ВЫТЕСНЯЕТ.
# Иначе «свой раньше свободного» превратилось бы в «все на первый слот».
other = lease_as(roomy, "K-other", "vol-two", new_key()).json()
check("другая установка при свободных слотах занимает свободный",
      other["slot_no"] == 2 and slots_of("roomy")["occupied"] == 2,
      f"слот {other['slot_no']}")

# ── ВОРКЕРЫ ОДНОГО СТАРТА НЕ ФЕНСЯТ ДРУГ ДРУГА ЧЕРЕЗ ПЕРЕЗАЯВКУ ───────────
# Перезаявляет ОДИН воркер, а эпох поднимается у ВСЕГО поколения; привязки
# братьев остаются на прежнем номере. Пока фенсинг судил по строке аренды
# каждого ключа, контейнер, ДЕРЖАЩИЙ слот, темнел на всех воркерах, кроме
# перезаявившего, — и отказ дословно называл его же старт «более новым
# запуском». Раскатка K8s на одном PVC с двумя воркерами в поде попадала в это
# штатно. Краснеет возвратом сверки на `binding["epoch"]`.
siblings = issue("siblings")
sib_one, sib_two = new_key(), new_key()
lease_as(siblings, "POD", "vol-one", sib_one)
lease_as(siblings, "POD", "vol-one", sib_two)
meter_as(siblings, sib_one)                            # первый квант обоих воркеров
meter_as(siblings, sib_two)
lease_as(siblings, "OTHER", "vol-two", new_key())      # вытеснил поколение POD
check("вытесненный воркер отфенсен", meter_as(siblings, sib_one).status_code == 409)
lease_as(siblings, "POD", "vol-one", sib_one)          # ОДИН воркер перезаявил
check("перезаявка одного воркера вернула слот всему поколению",
      slots_of("siblings")["slots"][0]["holder"]["start_id"] == "POD")
check("и БРАТ того же старта покупает, а не темнеет",
      meter_as(siblings, sib_two).status_code == 200,
      "фенсит поколение, а не строка аренды воркера")

# ── ПУСТОЙ СЛОТ НЕ НАЗЫВАЕТ ДЕРЖАТЕЛЯ ─────────────────────────────────────
# Понижение тарифа и возврат обратно снимают `retired`, но эпох уже поднят, а
# держателя нет. Общий текст говорил «место занял более новый запуск того же
# тарифа … слышали 0 с назад» про ПУСТОЙ слот — тот самый совет, который
# опровергается собственным экраном клиента (Б26).
empty = issue("emptyslot", "work")
empty_keys = [new_key() for _ in range(4)]
for number, process in enumerate(empty_keys):
    lease_as(empty, f"E{number}", f"vol-{number}", process)
    meter_as(empty, process)                           # первый квант — внутри acquire()
admin.post("/admin/replan", json={"org_id": "emptyslot", "plan": "start"}, headers=ADMIN)
admin.post("/admin/replan", json={"org_id": "emptyslot", "plan": "work"}, headers=ADMIN)
orphan = meter_as(empty, empty_keys[2])
check("отказ по слоту без держателя не выдумывает более новый запуск",
      orphan.status_code == 409
      and "занял более новый запуск" not in orphan.json().get("detail", ""),
      orphan.json().get("detail", "")[:90])

# ── ПОТОЛОК ЧАСТОТЫ РЕЖЕТ ИМЕННО ОТФЕНСЕННЫЙ ТРАФИК ───────────────────────
# §3.4 ТЗ закладывает, что отфенсенный ВЫПУЩЕННЫЙ движок повторяет `/v1/meter`
# каждый тик до продления (до восьми часов), и §7 переводит в это состояние
# весь флот на время миграции. Потолок читал `meter.updated_at`, а его двигает
# только УСПЕШНАЯ покупка — то есть резал кого угодно, кроме этого трафика.
flood = issue("flood")
flood_key = new_key()
lease_as(flood, "F1", "vol-one", flood_key)
meter_as(flood, flood_key)                             # первый квант — внутри acquire()
time.sleep(1.05)                                       # потолок частоты — ровно секунда
lease_as(flood, "F2", "vol-two", new_key())
storm = [public.post("/v1/meter", json={"key": flood, "pubkey": flood_key,
                                        "nonce": "f"}).status_code
         for _ in range(20)]
check("двадцать покупок отфенсенного подряд — не двадцать обращений к хранилищу",
      storm.count(429) >= 18 and storm[0] == 409,
      f"429 = {storm.count(429)}, первый {storm[0]}")

# ── ОТМЕТКУ СЛОТА СТАВИМ МЫ, А НЕ ПОЛЯ ТЕЛА ОТЧЁТА ────────────────────────
# `slot_no`/`epoch` лежали в `/v1/usage` ВЕРХНЕУРОВНЕВО, вне подписи отчёта, и
# сервер не сверял их ни с чем: ключ, держащий слот 2, двигал отметку слота 1
# соседнего поколения. Отметка — единственный вход ранжирования 2c, поэтому
# подделка позволяла держать мёртвый слот «свежим» и заставлять пришедшее
# поколение вытеснить ЖИВОГО соседа вместо трупа.
spoof = issue("spoof", "work")
spoof_one, spoof_two = new_key(), new_key()
lease_as(spoof, "SP1", "vol-one", spoof_one)
lease_as(spoof, "SP2", "vol-two", spoof_two)


def _heard(org: str, slot_no: int) -> float:
    row = server.STORE._fetchone(
        "SELECT last_heard_at FROM slots WHERE org_id=? AND slot_no=?",
        (org, slot_no))
    return float(row[0] or 0.0)


heard_before = _heard("spoof", 1)
time.sleep(0.05)
spoofed = public.post("/v1/usage", json={
    "key": spoof, "instance_id": "vol-two", "pubkey": spoof_two,
    "usage": {"requests": 1, "entities": {}}, "slot_no": 1, "epoch": 1})
check("чужой ключ не двигает отметку слота, который держит не он",
      spoofed.status_code == 200 and _heard("spoof", 1) == heard_before,
      f"было {heard_before}, стало {_heard('spoof', 1)}")
check("а свою отметку тот же отчёт двигает — без единого поля в теле",
      _heard("spoof", 2) > heard_before,
      "выпущенный флот этих полей не шлёт вовсе")

# ── ОТОЗВАННЫЙ КЛЮЧ СТАРШЕГО ТАРИФА НЕ ДЕРЖИТ ЧИСЛО СЛОТОВ ────────────────
# `org_plan` брал самый щедрый тариф среди ВСЕХ ключей организации без фильтра
# по статусу: понижение отзывом ключа (или выдачей через /admin/issue мимо
# /admin/replan) не доходило до потолка вовсе.
downgraded = issue("downgraded", "industrial")
row = server.STORE._fetchone(
    "SELECT key_hash FROM keys WHERE org_id=? AND plan=?", ("downgraded", "industrial"))
admin.post("/admin/revoke_key", json={"key_hash": row[0]}, headers=ADMIN)
# И ПОТОЛОК ПЕРЕСЧИТЫВАЕТСЯ В МОМЕНТ ОТЗЫВА, А НЕ ЖДЁТ ЧЬЕЙ-ТО АРЕНДЫ. Строки
# `slots` оставались от «Промышленного» до следующей аренды, и всё это время
# экран отдавал двенадцать живых слотов при `slot_count` один — занятость,
# способная превысить потолок, это тот же дефект Б26bis.
straight_after = slots_of("downgraded")
check("отзыв ключа сразу сводит живые слоты к новому тарифу",
      len(straight_after["slots"]) == straight_after["slot_count"] == 1,
      f"живых слотов {len(straight_after['slots'])} при "
      f"slot_count {straight_after['slot_count']}")
smaller = issue("downgraded", "start")
after_revoke = lease_as(smaller, "D1", "vol-one", new_key()).json()
check("отозванный ключ больше не задаёт число слотов",
      after_revoke["slot_count"] == 1, f"slot_count {after_revoke['slot_count']}")

# ── ОТФЕНСЕННОЕ ДО ПЕРВОЙ ПОКУПКИ НАЗВАНО НА ЭКРАНЕ ───────────────────────
# `draining` фильтровался по `band_left_estimate > 0`, и поколение, у которого
# соперник занял слот МЕЖДУ арендой и первым квантом, исчезало с экрана
# целиком: контейнер поднялся, `/mask` отдаёт 503, а оператор не находит о нём
# ни строчки. Именно нулевая полоса и значит «не обслуживает».
coldstart = issue("coldstart")
cold_key = new_key()
lease_as(coldstart, "COLD", "vol-one", cold_key)
lease_as(coldstart, "RIVAL", "vol-two", new_key())
cold_view = slots_of("coldstart")["slots"][0]
check("поколение с нулевой полосой названо в draining, а не пропало",
      [row["start_id"] for row in cold_view["draining"]] == ["COLD"],
      f"{cold_view['draining']}")

# ── S-18. /v1/release НИЧЕГО НЕ РЕШАЕТ ────────────────────────────────────
# Это единственное правило, которое разом выполняет Б26quinquies («честный уход
# не стоит ничего») и требование конструкции («прощание не нужно»).
quiet = issue("quiet")
quiet_key = new_key()
lease_as(quiet, "Q1", "vol-one", quiet_key)
before_release = slots_of("quiet")["slots"][0]
release_as(quiet, "vol-one", quiet_key)
after_release = slots_of("quiet")["slots"][0]
check("после /v1/release слот тот же, эпох тот же, держатель тот же",
      before_release["epoch"] == after_release["epoch"]
      and before_release["holder"]["start_id"] == after_release["holder"]["start_id"],
      f"{before_release['epoch']} -> {after_release['epoch']}")
check("но прощание ЗАПИСАНО — экран имеет право сказать «остановлен сам»",
      after_release["holder"]["released"] is True)

# ── S-19. /admin/release — РЫЧАГ ПОДДЕРЖКИ ────────────────────────────────
lever = issue("lever")
lever_key = new_key()
lease_as(lever, "L1", "vol-one", lever_key)
meter_as(lever, lever_key)                             # первый квант — внутри acquire()
freed = admin.post("/admin/release", json={"org_id": "lever", "instance_id": "vol-one"},
                   headers=ADMIN).json()
after_lever = slots_of("lever")["slots"][0]
lever_meter = meter_as(lever, lever_key)
check("поддержка поднимает эпох и освобождает слот установки",
      freed.get("slots") == 1 and after_lever["holder"] is None
      and after_lever["epoch"] == 2, f"{freed}, эпох {after_lever['epoch']}")
check("и держатель узнаёт об этом на ПОКУПКЕ, доцеживая купленное",
      lever_meter.status_code == 409
      and lever_meter.json().get("error") == "fenced",
      f"{lever_meter.status_code}")
missing = admin.post("/admin/release", json={"org_id": "lever", "instance_id": "нет"},
                     headers=ADMIN).json()
check("а «такой установки нет» — это ноль, а не успех",
      missing.get("slots") == 0 and missing.get("released") is False, f"{missing}")

# РЫЧАГ УМЕЕТ НАЗВАТЬ ОДИН СЛОТ, А НЕ ТОЛЬКО ВСЕ.
#
# Освобождались ВСЕ слоты установки, а установка у клиента одна на том: на
# тарифе, где несколько контейнеров подняты с одним `PSEUDEX_INSTANCE_ID` (E7,
# законная конфигурация), обращение «застрял один контейнер» отфенсивало все.
# Поддержка не имела формы задать вопрос уже — и отвечала самым крупным из
# доступных ей ответов.
one = issue("onelever", "work")
one_keys = []
for number in range(3):
    process = new_key()
    lease_as(one, f"OL{number}", "shared-vol", process)   # ОДНА установка, три старта
    meter_as(one, process)
    one_keys.append(process)
before_lever = slots_of("onelever")["occupied"]
picked = slots_of("onelever")["slots"]
target = next(row["slot_no"] for row in picked if row["holder"])
spot = admin.post("/admin/release",
                  json={"org_id": "onelever", "instance_id": "shared-vol",
                        "slot_no": target}, headers=ADMIN).json()
after_lever = slots_of("onelever")
check("поддержка освобождает НАЗВАННЫЙ слот, а не все слоты установки",
      spot.get("slots") == 1 and after_lever["occupied"] == before_lever - 1,
      f"освобождено {spot.get('slots')}, занято {before_lever} -> "
      f"{after_lever['occupied']}")
# И ПОМЕТКА «ОСВОБОДИЛА ПОДДЕРЖКА» СТОИТ ТОЛЬКО У ТОГО, КОГО ОНА ОСВОБОДИЛА.
# Пометка шла по `installation_id`, и один вызов переписывал причину и дату
# КАЖДОМУ прошлому запуску этого тома: давно вытесненные обычной перезаявкой
# поколения всплывали в списке доцеживающих с чужим словом. Слово рядом с
# числом не имеет права спорить с числом (Б26bis).
admin_marked = [row["start_id"] for slot in after_lever["slots"]
                for row in slot["draining"] if row["fenced_by"] == "admin"]
check("и только одно поколение подписано «освободила поддержка»",
      len(admin_marked) == 1, f"подписаны: {admin_marked}")

# ── S-20. ФОРМА /admin/instances ──────────────────────────────────────────
shape = slots_of("normal")
check("ответ описан слотами и несёт все поля формы",
      {"org_id", "slot_count", "occupied", "slots", "generations_24h",
       "epochs_unacked_24h", "slot_contention_24h", "window_seconds",
       "meter_target_seconds", "pending_installations", "unbound_processes",
       "unbound_granted"} <= set(shape), f"{sorted(shape)}")
gone = [word for word in ("silent", "reclaimed", "held_places", "live_processes",
                          "turnover", "alive_seconds")
        if word in json.dumps(shape)]
check("и ни одного слова удалённых механизмов", not gone, f"осталось: {gone}")
check("занято считается по держателям слотов",
      shape["occupied"] == sum(1 for row in shape["slots"] if row["holder"]),
      f"{shape['occupied']}")
# ЁМКОСТЬ БЕЗ ПРИВЯЗКИ НАЗВАНА ЧИСЛОМ, А НЕ ОСТАВЛЕНА В ЛОГЕ. Ключ без аренды в
# окне покупает и не фенсится (бандла у него нет, квант ему бесполезен), но тег
# слота у его строки пуст — значит агрегаты по слотам его не видят по
# построению, и без этой пары чисел выданное не видно НИГДЕ. §2 Т1 обещает
# «каждый обход виден числом».
stray = issue("stray")
stray_key = new_key()
public.post("/v1/meter", json={"key": stray, "pubkey": stray_key, "nonce": "s"})
stray_view = slots_of("stray")
check("ёмкость, купленная без привязанной аренды, названа отдельным числом",
      stray_view["unbound_processes"] == 1 and stray_view["unbound_granted"] > 0,
      f"процессов {stray_view['unbound_processes']}, "
      f"выдано {stray_view['unbound_granted']}")
check("и у привязанного клиента это число ноль — оно не шум, а сигнал",
      shape["unbound_processes"] == 0, f"{shape['unbound_processes']}")

# ── S-22. АНОМАЛИИ СЧИТАЮТ ТЕМИ ЖЕ ЕДИНИЦАМИ, ЧТО ЛЕДЖЕР ──────────────────
# Урок Б26bis: наблюдение и ограничитель, разошедшиеся в единицах, — это два
# ответа на один вопрос.
honest_org = issue("honest")
honest_key = new_key()
lease_as(honest_org, "H1", "vol-one", honest_key)
meter_as(honest_org, honest_key)
listed = {row["org_id"] for row in
          admin.get("/admin/anomalies", headers=ADMIN).json().get("anomalies", [])}
check("кольцо и клон тома в отчёте, один запуск без перезаявок — нет",
      {"ring", "clone"} <= listed and "honest" not in listed,
      f"в отчёте: {sorted(listed)}")
# И ЭТО НЕ ЛОЖНАЯ ТРЕВОГА, А ОБЪЯВЛЕННЫЙ ПОРОГ: десять запусков за сутки на
# тарифе в один контейнер, ни один из которых не подтвердил расхода, — это либо
# кольцо, либо клиент, у которого контейнеры падают и он об этом не знает. И то
# и другое мы обязаны увидеть первыми, а не прочесть в письме.
check("а crash-loop честного клиента попадает в отчёт НАМЕРЕННО",
      "restart" in listed,
      "десять поколений без единого подтверждённого расхода — порог § 3.7")

# ЧЕСТНАЯ РАСКАТКА — НЕ АНОМАЛИЯ, И ЭТО ДВЕ ОТДЕЛЬНЫЕ ПРИЧИНЫ СРАЗУ.
# `epochs_unacked` джойнил `generations.epoch` на `meter.epoch`, а тег строки
# леджера двигается только на СЛЕДУЮЩЕЙ покупке: поколение, подтвердившее
# подписанным ack сто восемьдесят запросов, после своей единственной
# разрешённой перезаявки читалось как «не подтвердило ничего». А порог
# `slot_contention ≥ 1` срабатывал на той самой одной перезаявке, про которую
# его же текст пишет «честный движок делает одну». Одна раскатка K8s (§4.4 —
# «штатно, при каждом обновлении») клала клиента в отчёт с формулировкой
# «кольцо или крэшлуп».
rolled = issue("rolled")
rolled_key, rolled_new = new_key(), new_key()
lease_as(rolled, "R-OLD", "vol-one", rolled_key)
meter_as(rolled, rolled_key)
_secret = server.STORE.report_secret("rolled", rolled_key)
_ack = {"consumed": 180, "slot_no": 1, "epoch": 1}
_ack["signature"] = mac_report(_ack, bytes.fromhex(_secret))
time.sleep(1.05)
signed = public.post("/v1/meter", json={"key": rolled, "pubkey": rolled_key,
                                        "nonce": "sig", "ack": _ack})
check("подписанный ack принят и расход записан",
      signed.status_code == 200
      and server.STORE.billable("rolled")["acked"] == 180,
      f"{signed.status_code}, acked={server.STORE.billable('rolled')['acked']}")
lease_as(rolled, "R-NEW", "vol-one", rolled_new)   # новый под той же установки
meter_as(rolled, rolled_new)
# Новый под ещё не отчитывался, поэтому ОДНО поколение без подтверждения —
# правда. Проверяется, что перезаявка вытесненного к нему НЕ прибавляет.
unacked_before = slots_of("rolled")["epochs_unacked_24h"]
lease_as(rolled, "R-OLD", "vol-one", rolled_key)   # вытесненный вернулся ОДИН раз
rolled_view = slots_of("rolled")
check("перезаявка не стирает подтверждённый расход поколения",
      rolled_view["epochs_unacked_24h"] == unacked_before == 1,
      f"epochs_unacked {unacked_before} -> {rolled_view['epochs_unacked_24h']} "
      f"при подтверждённых 180 у вернувшегося")
rolled_listed = {row["org_id"] for row in
                 admin.get("/admin/anomalies", headers=ADMIN).json().get("anomalies", [])}
check("и одна честная раскатка не попадает в аномалии",
      "rolled" not in rolled_listed, f"в отчёте: {sorted(rolled_listed)}")

# ОБЩИЙ PSEUDEX_START_ID БОЛЬШЕ НЕ СНИМАЕТ ФЕНСИНГ — ИМЯ ПОКОЛЕНИЯ ЧЕКАНИМ МЫ.
#
# Поколение искалось по одному клиентскому `start_id`, и шаг «это ещё один
# воркер того же старта» отдавал нашедшему ТОТ ЖЕ слот и ТОТ ЖЕ эпох даром.
# Пять контейнеров на пяти РАЗНЫХ томах, поднятых с одной переменной, были по
# нашим записям одним поколением: все пятеро покупали одновременно, ни один не
# был отфенсен, и §3.3 «на слоте покупает ровно одно поколение» переставало
# быть верным от одной переменной окружения. Замер до правки: пять раз 200.
#
# Теперь заявка из-под ДРУГОЙ установки в чужое поколение не попадает — она
# получает имя, которое чеканим мы, свой эпох и обычный фенсинг. Краснеет
# возвратом `_generation_name` к тождеству.
shared = issue("shared")
shared_keys = [new_key() for _ in range(5)]
for number, process in enumerate(shared_keys):
    lease_as(shared, "ONE-START", f"vol-{number}", process)
    meter_as(shared, process)                  # первый квант — внутри acquire()
later = [meter_as(shared, process).status_code for process in shared_keys]
check("общий start_id с РАЗНЫХ томов фенсится: покупает один, четверо — 409",
      later.count(409) == 4 and later.count(200) == 1, f"{later}")
holder_epoch = slots_of("shared")["slots"][0]["epoch"]
check("и эпох поднят пять раз, а не остался единицей на всех",
      holder_epoch == 5, f"эпох {holder_epoch}")
shared_reasons = [row for row in
                  admin.get("/admin/anomalies", headers=ADMIN).json().get("anomalies", [])
                  if row["org_id"] == "shared"]
check("а само событие названо: пять установок под одним именем старта",
      bool(shared_reasons)
      and shared_reasons[0]["installations_per_generation"] == 5,
      f"{shared_reasons[:1]}")

# ОСТАТОК, КОТОРЫЙ ЭТИМ НЕ ЗАКРЫВАЕТСЯ, НАЗВАН ЗДЕСЬ ЧИСЛОМ, А НЕ УМОЛЧАНИЕМ.
# Контейнер, назвавший И чужой `start_id`, И чужой `installation_id`, неотличим
# от восьмого воркера того же старта: сервер получает байты, а «я тот же
# контейнер» — утверждение клиента (§1.2 ТЗ в применении к личности). Такие
# покупают одновременно и после правки — это класс «параллелизм бесплатен,
# объём оплачен» (§8.1), и он закрывается договором, а не техникой.
twins = issue("twins")
twin_keys = [new_key() for _ in range(3)]
for process in twin_keys:
    lease_as(twins, "SAME", "same-vol", process)
twin_bought = [meter_as(twins, process).status_code for process in twin_keys]
check("ОСТАТОК: тот же start_id И тот же том — одно поколение, все покупают",
      twin_bought == [200] * 3,
      "неотличимо от трёх воркеров одного контейнера; закрывает оферта §5bis")

# ── ЧЕСТНАЯ РАСКАТКА НА emptyDir НЕ АНОМАЛИЯ ──────────────────────────────
# `installations_per_slot` считал установки НА СЛОТ, а под на `emptyDir` — это
# новый том, то есть новая установка на том же слоте. ТЗ §4.4 называет такую
# раскатку штатной, и клиент, катящийся раз в день, попадал в аномалии каждый
# день с формулировкой про клон тома. Аномалия, срабатывающая на поведении,
# которое ТЗ объявило нормальным, — шум, а не наблюдение.
ephemeral = issue("ephemeral")
for number in range(3):
    process = new_key()
    lease_as(ephemeral, f"POD-{number}", f"ephemeral-{number}", process)
    meter_as(ephemeral, process)               # первый квант — внутри acquire()
    time.sleep(1.05)                           # потолок частоты — ровно секунда
    meter_as(ephemeral, process, consumed=120)  # и подтверждённый расход
listed_orgs = {row["org_id"] for row in
               admin.get("/admin/anomalies", headers=ADMIN).json().get("anomalies", [])}
check("три раскатки на новых томах подряд — ни одной аномалии",
      "ephemeral" not in listed_orgs, f"в отчёте: {sorted(listed_orgs)}")

# ТАБЛИЦА ПОКОЛЕНИЙ ЧИСТИТСЯ, А ДЕРЖАТЕЛЬ НИКОГДА НЕ ВЫЧИЩАЕТСЯ.
# Строка пишется на КАЖДЫЙ старт контейнера, а `/admin/instances` читает их все;
# крэшлуп ТЗ считает ожидаемым трафиком. Удалить строку держателя значило бы
# забыть, чей это слот: `meter_if_allowed` перестал бы находить его положение.
swept = issue("swept")
sweep_key = new_key()
for number in range(5):
    lease_as(swept, f"SW{number}", "vol-one", sweep_key if number == 4 else new_key())
server.STORE._conn.execute("UPDATE generations SET last_lease_at=0 WHERE org_id=?",
                           ("swept",))
server.STORE._conn.commit()
server.STORE.prune_leases(86400)
left = server.STORE._fetchall(
    "SELECT start_id FROM generations WHERE org_id=?", ("swept",))
check("старые поколения вычищены, держатель остался",
      [row[0] for row in left] == ["SW4"], f"{[row[0] for row in left]}")
check("и держатель по-прежнему покупает ёмкость",
      meter_as(swept, sweep_key).status_code == 200,
      "иначе чистка забыла бы, чей это слот")

# ── S-23. СЧЁТ НЕ СДВИНУЛСЯ: СЛОТ И ЭПОХ — ТЕГ, А НЕ ВХОД АРИФМЕТИКИ ──────
# Леджер остался ПО ПРОЦЕССУ (§3bis.2): наследование остатка на слот прятало бы
# обороты кольца и делало бы перезапуск платным. Проверяется буквально: тег
# строки можно переписать любым, и `billable` не шелохнётся.
billed_before = server.STORE.billable("rolled")
server.STORE._conn.execute("UPDATE meter SET slot_no=99, epoch=99 WHERE org_id=?",
                           ("rolled",))
server.STORE._conn.commit()
check("счёт считается по процессу — тег на него не влияет",
      server.STORE.billable("rolled") == billed_before, f"{billed_before}")
server.STORE._conn.execute("UPDATE meter SET slot_no=1 WHERE org_id=?", ("rolled",))
server.STORE._conn.commit()

# ── S-24. СМЕНА ТАРИФА ────────────────────────────────────────────────────
# ТАРИФ «work» В ЭТОМ ФАЙЛЕ УЖЕ ПРАВЛЕН ВЫШЕ (max_instances 9), поэтому здесь
# берутся нетронутые: «Промышленный» (12) вниз до «Старта» (1).
replan = issue("replan", "industrial")
wide_count = server.STORE.instances_allowed("industrial")
keys_by_slot = {}
for number in range(4):
    process = new_key()
    got = lease_as(replan, f"P{number}", f"vol-{number}", process).json()
    keys_by_slot[got["slot_no"]] = process
    meter_as(replan, process)                  # первый квант — внутри acquire()
admin.post("/admin/replan", json={"org_id": "replan", "plan": "start"}, headers=ADMIN)
shrunk = slots_of("replan")
# ВЫВОДЯТСЯ ПУСТЫЕ СЛОТЫ, А СРЕДИ ЗАНЯТЫХ — ТЕ, КОГО СЛЫШАЛИ РАНЬШЕ. Здесь
# заняты все четыре, поэтому выживает последний заявленный, а не первый по
# номеру: номер слота ничего не говорит о том, занят ли он.
survivor_slot = shrunk["slots"][0]["slot_no"]
retired_meter = meter_as(replan, keys_by_slot[min(keys_by_slot)])
check("понижение тарифа оставляет РОВНО столько слотов, сколько по тарифу",
      shrunk["slot_count"] == 1 and len(shrunk["slots"]) == 1,
      f"слотов {len(shrunk['slots'])}, выжил {survivor_slot}")
check("держатель выведенного слота отфенсен текстом про ТАРИФ, а не про соседа",
      retired_meter.status_code == 409
      and "тариф" in retired_meter.json().get("detail", "")
      and "новый запуск" not in retired_meter.json().get("detail", ""),
      retired_meter.json().get("detail", "")[:120])
# СОВЕТ «ОСТАНОВИТЕ ОДИН КОНТЕЙНЕР» ЕДЕТ С ЧИСЛАМИ, ПО КОТОРЫМ ЕГО МОЖНО
# ПРОВЕРИТЬ. Без них это Б26 в чистом виде: совет остановить то, чего клиент у
# себя не находит.
check("и отказ называет оба числа, а не советует на веру",
      "допускает 1" in retired_meter.json().get("detail", "")
      and "слышно 4" in retired_meter.json().get("detail", ""),
      retired_meter.json().get("detail", "")[:120])
check("а поля отказа не выдумывают держателя выведенного слота",
      "holder_start_id" not in retired_meter.json(),
      f"{sorted(retired_meter.json())}")

# ── ПОНИЖЕНИЕ ТАРИФА НЕ ФЕНСИТ ТОГО, КТО ОСТАЛСЯ ОДИН ─────────────────────
#
# Выводились слоты с НОМЕРОМ выше потолка, а номер слота ничего не говорит о
# том, занят ли он. Клиент поднимал три контейнера, два погасил, работающий
# остался на слоте 3 — и переход на «Старт» отправлял ЕДИНСТВЕННЫЙ живой
# контейнер в `fenced` текстом «остановите лишний контейнер», при том что
# слоты 1 и 2 держали трупы, а лишнего контейнера не было ни одного. Это
# дефект Б26, пришедший через тариф. Краснеет возвратом отбора в
# `ensure_slots` к `slot_no > allowed`.
lone = issue("lone", "industrial")
lone_key = None
for number in range(3):
    process = new_key()
    lone_slot = lease_as(lone, f"L{number}", f"vol-{number}", process).json()["slot_no"]
    meter_as(lone, process)
    lone_key = process                          # последний — тот, что остался жив
    time.sleep(1.05)                            # отметки слотов обязаны различаться
lone_meter_before = meter_as(lone, lone_key)    # живой продолжает говорить с нами
check("живой контейнер — на верхнем слоте, два прежних молчат",
      lone_slot == 3 and lone_meter_before.status_code == 200,
      f"слот {lone_slot}, покупка {lone_meter_before.status_code}")
admin.post("/admin/replan", json={"org_id": "lone", "plan": "start"}, headers=ADMIN)
lone_view = slots_of("lone")
time.sleep(1.05)
lone_meter = meter_as(lone, lone_key)
check("понижение тарифа оставляет слот тому, кого слышали позже всех",
      lone_view["occupied"] == 1 and lone_view["slot_count"] == 1
      and lone_view["slots"][0]["slot_no"] == lone_slot,
      f"занято {lone_view['occupied']} из {lone_view['slot_count']}, "
      f"слот {lone_view['slots'][0]['slot_no']} (живой был на {lone_slot})")
check("и живой контейнер покупает дальше — понижение тарифа его не отфенсило",
      lone_meter.status_code == 200,
      f"{lone_meter.status_code} {lone_meter.json().get('detail', '')[:80]}")
# И ВЫВЕДЕННЫЙ СЛОТ ТЕРЯЕТ ДЕРЖАТЕЛЯ СРАЗУ, А НЕ ПРИ ВОЗВРАТЕ ТАРИФА. Оставить
# его значило бы показать слот занятым поколением, которому мы уже отказали в
# новой ёмкости, — и после обратного повышения он приехал бы занятым трупом.
check("занято не превышает нового тарифа ни на одну строку",
      shrunk["occupied"] <= shrunk["slot_count"] == 1,
      f"занято {shrunk['occupied']} из {shrunk['slot_count']}")
admin.post("/admin/replan", json={"org_id": "replan", "plan": "industrial"},
           headers=ADMIN)
grown = slots_of("replan")
check("повышение возвращает слоты свободными, а эпох не откатывается",
      grown["slot_count"] == wide_count
      and grown["slots"][0]["epoch"] >= shrunk["slots"][0]["epoch"],
      f"слотов {grown['slot_count']} из {wide_count}, "
      f"эпох {shrunk['slots'][0]['epoch']} -> {grown['slots'][0]['epoch']}")

# ── S-12. СТАРЫЙ ДВИЖОК ПРОТИВ НОВОГО СЕРВЕРА ─────────────────────────────
# Сервер НЕ ТРЕБУЕТ ПОЛЯ НИКОГДА (D-063): ошибка совместимости — это простой у
# клиента. Движок без `start_id` ведётся в той же конструкции под синтетическим
# поколением `legacy:<установка>`, поэтому он не заперт и не получает
# бесплатного трафика.
legacy = issue("legacy")
legacy_codes = []
for number in range(5):
    process = new_key()
    legacy_codes.append(lease_as(legacy, None, "vol-one", process,
                                 version="1.0.0").status_code)
    legacy_codes.append(meter_as(legacy, process).status_code)
legacy_view = slots_of("legacy")
check("движок без start_id не заперт: пять перезапусков, ни одного отказа",
      set(legacy_codes) == {200}, f"коды {sorted(set(legacy_codes))}")
check("все его перезапуски — ОДНО синтетическое поколение одной установки",
      legacy_view["generations_24h"] == 1 and legacy_view["slots"][0]["epoch"] == 1,
      f"поколений {legacy_view['generations_24h']}, "
      f"эпох {legacy_view['slots'][0]['epoch']}")
legacy_second = new_key()
lease_as(legacy, None, "vol-two", legacy_second, version="1.0.0")
check("а второй ТОМ на тарифе в один слот фенсит первый — и это не отказ аренды",
      slots_of("legacy")["slots"][0]["epoch"] == 2,
      "чужая установка берёт слот по ранжированию, аренде отвечают 200")


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
time.sleep(1.1)
honest._meter_step()
served, _ = honest.capacity()
totals = server.STORE.billable("cap-honest")
check("честная цепь: к счёту ровно расход, а не потолок",
      totals["billable"] == served,
      f"расход {served}, к счёту {totals['billable']}, потолок {totals['granted']}")

# ПОВТОР УЖЕ ПРИНЯТОГО КВАНТА. Секунда паузы — из-за потолка частоты на самой
# ручке: он общий для всех и честного клиента не задевает, потому что тот
# приходит раз в четыре минуты на процесс.
time.sleep(1.1)
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
time.sleep(1.1)
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
time.sleep(1.1)
silent._meter_step()
quiet = server.STORE.billable("cap-silent")
check("снятый отчёт не занижает счёт и виден числом",
      quiet["billable"] >= spent and quiet["unacked_quanta"] > 0,
      f"расход {spent}, к счёту {quiet['billable']}, "
      f"квантов без отчёта {quiet['unacked_quanta']}")


# СНЯТЫЙ ПО ДОРОГЕ ОТЧЁТ — ЭТО ЗАПИСЬ У НАС. Ровно тот сценарий, который на
# живом стенде не двигал ни одного счётчика: подделать было видно, повторить
# видно, снять целиком — нет.
stripped_key = admin.post("/admin/issue", json={"org_id": "stripped", "plan": "start"},
                          headers=ADMIN).json()["key"]
stripped_pk = generate_process_key().public
opened = public.post("/v1/lease", json={
    "key": stripped_key, "instance_id": "s", "pubkey": stripped_pk,
    "engine_version": "1.0.0", "nonce": "one"}).json()
for _ in range(3):
    public.post("/v1/lease", json={
        "key": stripped_key, "instance_id": "s", "pubkey": stripped_pk,
        "engine_version": "1.0.0", "nonce": "two",
        "lease_id": opened["lease_id"]})   # продление БЕЗ поля usage
stripped_totals = admin.get("/admin/usage", params={"org_id": "stripped"},
                            headers=ADMIN).json()["usage"]
check("продление без отчёта считается, а не проходит тишиной",
      stripped_totals["reports_missing"] == 3,
      f"пропущенных отчётов {stripped_totals['reports_missing']}")


# НОЛЬ ЁМКОСТИ — БЕЗЛИМИТ ТОЛЬКО ДЛЯ СТАРОГО СЕРВЕРА. Иначе лазейка, убранная
# из STALE, возвращается другой дверью: движок взял аренду, наш сервер умер до
# первого кванта, `_granted` остался нулём — и обслуживание снова безлимитно на
# весь TTL плюс grace.
cold = LicenseClient(base_url=_base, key=server.STORE.issue_key("cap-cold", "start"),
                     instance_id="cold", ca_path="",
                     usage_provider=lambda: {"requests": 0, "entities": {}, "values": 0})
cold._capacity_endpoint = "/v1/meter"
legacy = LicenseClient(base_url=_base, key=server.STORE.issue_key("cap-old", "start"),
                       instance_id="old", ca_path="",
                       usage_provider=lambda: {"requests": 0, "entities": {}, "values": 0})
check("нулевая ёмкость — безлимит только для сервера контракта 2",
      not cold.has_capacity() and legacy.has_capacity(),
      f"контракт 3: {cold.has_capacity()}, контракт 2: {legacy.has_capacity()}")

started = engine("cap-start", "start")
check("после acquire ёмкость есть сразу, а не с первого тика петли",
      started.capacity()[1] > 0, f"ёмкость {started.capacity()}")


# ДВА СООБЩЕНИЯ — ДВА КАНОНИЧЕСКИХ ВИДА. Один общий был приглашением спутать
# лизу с отчётом, а исключённое имя `bundle` означало, что поле с таким именем в
# ОТЧЁТЕ окажется вне MAC.
import hmac as _hmac  # noqa: E402
import hashlib as _hashlib  # noqa: E402

from pseudex.bundle import (mac_report, signing_payload,  # noqa: E402
                            verify_report)

_secret = b"k" * 32
_report = {"requests": 5, "values": 2}
_new = dict(_report); _new["signature"] = mac_report(_new, _secret)
_old = dict(_report)
_old["signature"] = _hmac.new(_secret, signing_payload(_old),
                              _hashlib.sha256).hexdigest()
_forms = []
for name, candidate in (("новая", _new), ("старая", _old)):
    try:
        verify_report(candidate, _secret)
        _forms.append(name)
    except BundleError:
        pass
_tampered = dict(_new); _tampered["bundle"] = "подсунуто"
try:
    verify_report(_tampered, _secret)
    _outside = True
except BundleError:
    _outside = False
check("обе формы MAC отчёта принимаются, пока в парке есть старые движки",
      _forms == ["новая", "старая"], f"приняты: {_forms}")
check("поле `bundle` в отчёте больше не вне подписи", not _outside)


# --- МОСТ МЕЖДУ КОНТРАКТАМИ, В ОБЕ СТОРОНЫ --------------------------------
# Правило выката (`operations.md` §2bis) держится ровно на этом: сервер первым,
# движок потом. Проверяется, что первое направление безопасно, а второе
# отказывает ВНЯТНО, а не выглядит как наш сбой.
from pseudex.bundle import decode_public_key, verify_lease  # noqa: E402

legacy_key = server.STORE.issue_key("bridge-old", "start")
legacy_pk = generate_process_key().public
legacy_lease = httpx.post(f"{_base}/v1/lease", timeout=60, json={
    "key": legacy_key, "instance_id": "i", "pubkey": legacy_pk,
    "engine_version": "1.0.0"}).json()          # БЕЗ nonce — так ходит контракт 2
signature_holds = True
try:
    verify_lease(legacy_lease, decode_public_key(server.PUBLIC_KEY))
except BundleError:
    signature_holds = False
check("движок контракта 2 работает против сервера контракта 3 без изменений",
      signature_holds and "bundle" in legacy_lease
      and legacy_lease.get("requests_granted")
      and server.STORE.granted_total("bridge-old") > 0,
      f"грант по времени (мост) = {server.STORE.granted_total('bridge-old')}")

modern = LicenseClient(base_url=_base, key=server.STORE.issue_key("bridge-new", "start"),
                       instance_id="j", ca_path="",
                       usage_provider=lambda: {"requests": 0, "entities": {}, "values": 0})
modern._pending_nonce = "expected"
try:
    modern._apply(dict(legacy_lease))           # ответ сервера контракта 2
    refused, reason = False, ""
except BundleError as error:
    refused, reason = True, str(error)
check("движок контракта 3 против сервера контракта 2 отказывается, назвав причину",
      refused and "contract 3" in reason and "deploy it FIRST" in reason,
      reason[:80])

# --- СКРЕЙП: ИСХОДЫ СЧИТАЮТСЯ, И ЦЕПЬ ВИДНА НЕ ТОЛЬКО В КОНСОЛИ ----------
#
# Доля 402/403 на `/v1/lease` описана в `docs/operations.md` §5 и была там
# помечена «не реализовано». Проверяется не наличие ручки, а то, что счётчик
# ДВИГАЕТСЯ на настоящем отказе: метрика, которая всегда ноль, — это описание
# метрики, а не метрика.
print("\nСКРЕЙП")


def _scrape() -> str:
    response = admin.get("/admin/metrics", headers=ADMIN)
    return response.text if response.status_code == 200 else f"HTTP {response.status_code}"


def _sample(text: str, needle: str) -> float | None:
    for line in text.splitlines():
        if line.startswith(needle) and not line.startswith("#"):
            return float(line.rsplit(" ", 1)[1])
    return None


before = _sample(_scrape(), 'pseudex_license_responses_total{path="/v1/lease",code="403"}') or 0
refused = public.post("/v1/lease", json={"key": "ps_live_no_such_key",
                                         "pubkey": generate_process_key().public})
after_text = _scrape()
after = _sample(after_text, 'pseudex_license_responses_total{path="/v1/lease",code="403"}') or 0
check("отказ аренды считается по коду, а не теряется в ветке обработчика",
      refused.status_code == 403 and after == before + 1,
      f"{before} -> {after}, ответ {refused.status_code}")

# Middleware считает ВСЁ /v1/*, включая успех: без знаменателя доля 402/403
# неотличима от единицы — делить не на что.
public.get("/v1/pubkey")
check("успех тоже считается, иначе у доли 402/403 нет знаменателя",
      (_sample(_scrape(), 'pseudex_license_responses_total{path="/v1/pubkey",code="200"}') or 0) >= 1)

scrape = _scrape()
# Заголовок HELP/TYPE — по ОДНОМУ на имя. Второй такой же Prometheus считает
# дубликатом и роняет скрейп ЦЕЛИКОМ: одна кривая строка убивает не свою
# метрику, а все.
names = [line.split()[2] for line in scrape.splitlines() if line.startswith("# TYPE ")]
check("ни одно имя метрики не объявлено дважды", len(names) == len(set(names)),
      str([n for n in names if names.count(n) > 1]))
check("в скрейпе нет ни ключей, ни токенов",
      "ps_live_" not in scrape and "test-admin" not in scrape and "test-shop" not in scrape)
check("сводка по флоту отвечает на вопросы, ради которых заведена",
      all(metric in scrape for metric in
          ("pseudex_chain_breaks_total", "pseudex_instances_serving",
           "pseudex_unverified_reports_total", "pseudex_reports_missing_total")))

# СЧИТАЮТСЯ ЛИЧНОСТИ, А НЕ СТРОКИ. `lease_id` свежий на каждом продлении, и
# `COUNT(*)` завысил бы флот втрое: при TTL сутки и продлении через треть TTL
# один живой воркер оставляет в окне три-четыре строки. Ошибиться здесь значит
# рассказывать себе, что клиентов втрое больше, чем есть.
for _renewal in range(3):
    for _worker in ("age1metric-a", "age1metric-b"):
        server.STORE.lease_generation(
            f"ls_metric_{_renewal}_{_worker}", "fleet-org", "start",
            "start-metric", "fleet-inst", _worker, 86400, pubkey=_worker)
fleet = server.STORE.fleet_totals(86400)
check("шесть строк аренды — это один контейнер и два воркера",
      fleet["instances_serving"] >= 1 and fleet["processes_serving"] >= 2,
      f"организаций={fleet['orgs_serving']} контейнеров={fleet['instances_serving']} "
      f"воркеров={fleet['processes_serving']}")
_by_pubkey = server.STORE.fleet_totals(86400)["processes_serving"]
for _renewal in range(3, 6):
    server.STORE.lease_generation(
        f"ls_metric_{_renewal}", "fleet-org", "start", "start-metric",
        "fleet-inst", "age1metric-a", 86400, pubkey="age1metric-a")
check("ещё три продления того же воркера флот не увеличивают",
      server.STORE.fleet_totals(86400)["processes_serving"] == _by_pubkey,
      f"{_by_pubkey} -> {server.STORE.fleet_totals(86400)['processes_serving']}")

# --- ОБРАЗ: СПИСОК COPY ПРОТИВ ТОГО, ЧТО РЕАЛЬНО ГРУЗИТСЯ ----------------
#
# `licensing/Dockerfile` копирует модули `pseudex/` ПОИМЁННО — намеренно, чтобы
# движок не уехал в образ лицензий целиком. Цена в том, что новый импорт ломает
# не тест, а ОБРАЗ: `metrics.py` приехал вместе со скрейпом, в списке его не
# было, и боевой контейнер лицензий не стартовал бы вовсе — единственный отказ,
# после которого весь флот начинает жечь grace. Увидеть это можно было только
# собрав образ; теперь видно отсюда.
print("\nОБРАЗ ЛИЦЕНЗИОННОГО СЕРВЕРА")
_dockerfile = (Path(__file__).resolve().parent / "Dockerfile").read_text(encoding="utf-8")
_copied = {word.split("/")[-1] for word in _dockerfile.split()
           if word.startswith("pseudex/") and word.endswith(".py")}
#
# В ОТДЕЛЬНОМ ПРОЦЕССЕ, И ЭТО НЕ ПЕДАНТИЗМ: сам тест поднимает ещё и КЛИЕНТСКУЮ
# половину (`pseudex.license`, `assets`, `morph`), которой в образе лицензий
# делать нечего. Считать `sys.modules` здесь значило бы требовать в Dockerfile
# половину движка — то есть ровно то, ради предотвращения чего список поимённый.
_probe = subprocess.run(
    [sys.executable, "-c",
     "import sys, licensing.server; "
     "print(' '.join(sorted(n.split('.', 1)[1] + '.py' for n in sys.modules "
     "if n.startswith('pseudex.') and '.' not in n.split('.', 1)[1])))"],
    capture_output=True, text=True, timeout=300,
    cwd=str(Path(__file__).resolve().parent.parent), env=dict(os.environ))
_loaded = set(_probe.stdout.split())
check("всё, что грузит сервер, есть в COPY образа",
      bool(_loaded) and _loaded <= _copied,
      f"грузится {sorted(_loaded) or 'НИЧЕГО — проба не запустилась'}, "
      f"не скопировано: {sorted(_loaded - _copied) or 'ничего'}")


# ── РЕЕСТР ВЕРСИЙ В АРЕНДЕ (D-054…D-056, D-064) ───────────────────────────────
# Блок `version` едет ПОД подписью; развёрнутые движки 0.3.14 проверяют подпись
# по тому, что получили, — значит принимают его и игнорируют. 426 — вердикт,
# и только для закрытия, объявленного вовремя. Всё это против настоящего
# сервера, а реестр — файл, который подменяется на диске, как это делает агент.
print("\nРЕЕСТР ВЕРСИЙ В АРЕНДЕ")
import datetime as _dt  # noqa: E402
import json as _json  # noqa: E402
from licensing import registry as _registry  # noqa: E402

_reg_dir = tempfile.mkdtemp(prefix="pseudex-registry-")
_reg_path = os.path.join(_reg_dir, "releases.json")
_today = _dt.datetime.now(_dt.timezone.utc).date()
_digest = "sha256:" + "c" * 64


def _registry_doc(*, old_eol: str | None, old_announced: str | None) -> dict:
    return {
        "product": "pseudex", "schema": 1, "updated_at": "2026-09-20T00:00:00Z",
        "support": {"maintenance_months": 6, "eol_notice_days": 90},
        "cycles": [
            {"cycle": "0.4", "state": "current", "release_date": "2026-10-05",
             "eoas": None, "eol": None, "eol_announced": None,
             "latest": {"version": "0.4.2", "date": "2026-10-20", "digest": _digest},
             "aliases": ["0.4", "0", "latest"]},
            {"cycle": "0.3", "state": "eol" if old_eol and _dt.date.fromisoformat(old_eol) <= _today else "maintenance",
             "release_date": "2026-09-14", "eoas": "2026-10-05",
             "eol": old_eol, "eol_announced": old_announced,
             "latest": {"version": "0.3.17", "date": "2026-10-12", "digest": _digest},
             "aliases": ["0.3"]},
        ],
        "notices": [{"id": "n-1", "severity": "warning", "applies_to": ">=0.3.0 <0.3.17",
                     "text": "обновитесь", "url": "https://pseudex.ru/advisories/n-1"}],
    }


def _lease_for(engine_version: str, *, with_nonce: bool = False) -> httpx.Response:
    key = server.STORE.issue_key(f"reg-{engine_version}-{with_nonce}", "start")
    body = {"key": key, "instance_id": "i", "pubkey": generate_process_key().public,
            "engine_version": engine_version}
    if with_nonce:
        body["nonce"] = "n" * 32
    return httpx.post(f"{_base}/v1/lease", timeout=60, json=body)


def _signature_holds(lease: dict) -> bool:
    try:
        verify_lease(lease, decode_public_key(server.PUBLIC_KEY))
        return True
    except BundleError:
        return False


# 1. без реестра: блока нет, bundle_format есть, подпись сходится
server.REGISTRY = _registry.Watch("")
no_reg = _lease_for("0.3.14").json()
check("без реестра аренда идёт без блока version, но с bundle_format, и подпись сходится",
      "version" not in no_reg and no_reg.get("bundle_format") == server.BUNDLE_FORMAT
      and _signature_holds(no_reg), f"keys={sorted(k for k in no_reg if k != 'bundle')}")

# ── S-21. СЛОТ, ЭПОХ И ЧИСЛО СЛОТОВ — ПОД ПОДПИСЬЮ, КАК БЛОК `version` ─────
# Фенсинг-токен вне подписи — украшение: перехватчик переписал бы его, не тронув
# подписи. А выпущенный движок проверяет подпись ПО ТОМУ, ЧТО ПОЛУЧИЛ, и лишние
# ключи игнорирует, поэтому поля аддитивны и контракт остаётся третьим (D-063).
check("slot_no/epoch/slot_count едут ПОД подписью и не поднимают контракт",
      {"slot_no", "epoch", "slot_count"} <= set(no_reg)
      and no_reg.get("lease_contract", server.LEASE_CONTRACT) == server.LEASE_CONTRACT
      and _signature_holds(no_reg),
      f"слот {no_reg.get('slot_no')} эпох {no_reg.get('epoch')} "
      f"из {no_reg.get('slot_count')}")
_forged = dict(no_reg)
_forged["epoch"] = int(_forged["epoch"]) + 7
check("и подмена эпоха в пути ломает подпись, а не проходит молча",
      not _signature_holds(_forged),
      "иначе клиент принял бы за наш любой номер, который ему подсунули")

# 2. реестр есть; запрос в форме 0.3.14 (без nonce = контракт 2) → блок под подписью
_registry.dump(_registry_doc(old_eol=None, old_announced=None), _reg_path)
server.REGISTRY = _registry.Watch(_reg_path)
old_shape = _lease_for("0.3.14").json()
check("запрос в форме 0.3.14 получает подписанный блок version и проверяет его подпись",
      _signature_holds(old_shape) and old_shape.get("version", {}).get("latest") == "0.4.2"
      and old_shape["version"]["latest_in_cycle"] == "0.3.17"
      and old_shape["version"]["running_latest"] is False
      and old_shape["version"]["notice"]["id"] == "n-1",
      _json.dumps(old_shape.get("version"), ensure_ascii=False))

# 3. «1.0.0» — то, что говорил каждый образ до D-053 — старейший цикл, без отказа
legacy = _lease_for("1.0.0")
check("1.0.0 читается как старейший цикл и обслуживается",
      legacy.status_code == 200 and legacy.json()["version"]["latest_in_cycle"] == "0.3.17")

# 4. новейшая версия — running_latest, без дат
newest = _lease_for("0.4.2", with_nonce=True).json()
check("новейшая версия — running_latest и без deprecated/sunset",
      newest["version"]["running_latest"] is True and newest["version"]["deprecated_at"] is None
      and newest["version"]["sunset_at"] is None and newest["version"]["notice"] is None)

# 5. eol вчера, объявлен 100 дней назад → 426 unsupported_client с командой
_registry.dump(_registry_doc(old_eol=(_today - _dt.timedelta(days=1)).isoformat(),
                             old_announced=(_today - _dt.timedelta(days=100)).isoformat()), _reg_path)
refused = _lease_for("0.3.15")
check("после объявленного вовремя eol сервер отвечает 426 unsupported_client с min_supported и командой",
      refused.status_code == 426 and refused.json().get("error") == "unsupported_client"
      and refused.json().get("min_supported") == "0.4.2"
      and "pseudexctl upgrade --to 0.4" in refused.json().get("detail", ""),
      f"{refused.status_code} {refused.json()}")
served_new = _lease_for("0.4.2", with_nonce=True)
check("новейшая версия обслуживается, пока старый цикл закрыт", served_new.status_code == 200)

# 6. eol вчера, объявлен 10 дней назад → реестр НЕ ПРОХОДИТ валидацию при
#    загрузке, и сервер игнорирует его целиком: аренда выдана, блока нет, пола
#    нет, причина — в логе и в /admin/versions. Поздний eol не принуждается
#    никогда — даже ценой блока «есть новее» для всех, пока файл не починят.
_registry.dump(_registry_doc(old_eol=(_today - _dt.timedelta(days=1)).isoformat(),
                             old_announced=(_today - _dt.timedelta(days=10)).isoformat()), _reg_path)
late = _lease_for("0.3.15")
late_status = admin.get("/admin/versions", headers=ADMIN).json()["registry"]
check("eol, объявленный поздно, НЕ принуждается: реестр отвергнут целиком, аренда выдана без блока",
      late.status_code == 200 and "version" not in late.json()
      and late_status["loaded"] is False and "90 days" in (late_status["error"] or ""),
      f"{late.status_code} registry={late_status}")

# 8. метрика флота по версиям
metrics_text = admin.get("/admin/metrics", headers=ADMIN).text
check("метрика pseudex_fleet_instances{engine_version} есть",
      'pseudex_fleet_instances{engine_version="0.4.2"}' in metrics_text)

# 9. подмена файла на диске видна следующей аренде без рестарта
_registry.dump(_registry_doc(old_eol=None, old_announced=None), _reg_path)
reopened = _lease_for("0.3.15")
check("замена файла реестра видна следующей аренде без рестарта",
      reopened.status_code == 200 and reopened.json()["version"]["sunset_at"] is None)

# 7 (после восстановления файла). /admin/versions — флот по версиям и циклы реестра
versions = admin.get("/admin/versions", headers=ADMIN).json()
seen = {row["engine_version"] for row in versions["fleet"]}
check("/admin/versions показывает флот по версиям и реестр",
      versions["registry"]["loaded"] is True and {"0.3.14", "1.0.0", "0.4.2"} <= seen
      and versions["registry"]["latest"] == "0.4.2",
      f"fleet={sorted(seen)} registry={versions['registry']}")
check("/admin/versions закрыт витрине",
      admin.get("/admin/versions", headers={"Authorization": "Bearer test-shop"}).status_code == 403)

# 10. битый файл → блока нет, аренда идёт, подпись сходится
Path(_reg_path).write_text("{broken", encoding="utf-8")
broken = _lease_for("0.3.15").json()
check("битый реестр — аренда без блока version, не отказ", "version" not in broken and _signature_holds(broken))
server.REGISTRY = _registry.Watch("")

# ЛЕСТНИЦА НА КЛИЕНТЕ (D-055, D-063, D-064) — настоящий LicenseClient против
# настоящего сервера. Реестр строится ОТНОСИТЕЛЬНО версии этого чекаута: её
# цикл — в maintenance, следующий минор — current; иначе тест сломался бы на
# первом же бампе version.txt, не найдя ни одного дефекта.
print("\nЛЕСТНИЦА ВЕРСИЙ НА КЛИЕНТЕ")
from pseudex.assets import ASSETS as _ASSETS  # noqa: E402
from pseudex.license import ENGINE_VERSION as _ENGINE, LicenseError as _LicenseError, explain  # noqa: E402

_major, _minor, _patch = (int(part) for part in _ENGINE.split("-")[0].split("."))
_this_cycle = f"{_major}.{_minor}"
_next_latest = f"{_major}.{_minor + 1}.2"
_cycle_latest = f"{_major}.{_minor}.{_patch + 2}"


def _relative_doc(*, eol: str | None, announced: str | None) -> dict:
    return {
        "product": "pseudex", "schema": 1, "updated_at": "2026-09-20T00:00:00Z",
        "support": {"maintenance_months": 6, "eol_notice_days": 90},
        "cycles": [
            {"cycle": f"{_major}.{_minor + 1}", "state": "current", "release_date": "2026-10-05",
             "eoas": None, "eol": None, "eol_announced": None,
             "latest": {"version": _next_latest, "date": "2026-10-20", "digest": _digest},
             "aliases": [f"{_major}.{_minor + 1}", str(_major), "latest"]},
            {"cycle": _this_cycle,
             "state": "eol" if eol and _dt.date.fromisoformat(eol) <= _today else "maintenance",
             "release_date": "2026-09-14", "eoas": "2026-10-05",
             "eol": eol, "eol_announced": announced,
             "latest": {"version": _cycle_latest, "date": "2026-10-12", "digest": _digest},
             "aliases": [_this_cycle]},
        ],
        "notices": [{"id": "n-client", "severity": "warning",
                     "applies_to": f">={_this_cycle}.0 <{_cycle_latest}",
                     "text": "обновитесь", "url": "https://pseudex.ru/advisories/n-client"}],
    }


_announced = _today - _dt.timedelta(days=10)
_eol = _today + _dt.timedelta(days=200)
_registry.dump(_relative_doc(eol=_eol.isoformat(), announced=_announced.isoformat()), _reg_path)
server.REGISTRY = _registry.Watch(_reg_path)
ladder = engine("ladder", "start")
verdict = ladder.status()
_announced_unix = _dt.datetime(_announced.year, _announced.month, _announced.day,
                               tzinfo=_dt.timezone.utc).timestamp()
_eol_unix = _dt.datetime(_eol.year, _eol.month, _eol.day, tzinfo=_dt.timezone.utc).timestamp()
check("клиент разобрал подписанный блок version: есть новее, новейшая в цикле, пол",
      verdict.running_latest is False and verdict.latest == _next_latest
      and verdict.latest_in_cycle == _cycle_latest and verdict.min_supported == _cycle_latest,
      str(verdict))
check("@unix и HTTP-date разобраны в unix-секунды один раз, на клиенте",
      verdict.deprecated_at == _announced_unix and verdict.sunset_at == _eol_unix,
      f"deprecated_at={verdict.deprecated_at} ожидалось {_announced_unix}; "
      f"sunset_at={verdict.sunset_at} ожидалось {_eol_unix}")
check("уведомление по диапазону дошло до статуса с id, текстом и ссылкой",
      (verdict.notice or {}).get("id") == "n-client"
      and (verdict.notice or {}).get("url", "").startswith("https://"), str(verdict.notice))
check("клиент называет свою версию из одного источника",
      verdict.engine_version == _ENGINE)

# D-063: клиент заявил контракт, сервер записал — по этой колонке видно, когда
# мост контракта 2 можно снимать. Вторая строка той же версии — форма контракта 2
# (без nonce) — заводится ЗДЕСЬ, а не наследуется от литералов раздела выше: те
# совпадали с version.txt ровно до первого бампа, и проверка суммы по контрактам
# стала красной на merge-коммите Release PR 0.3.16, не найдя дефекта.
_lease_for(_ENGINE)
fleet = admin.get("/admin/versions", headers=ADMIN).json()["fleet"]
check("заявленный lease_contract записан рядом с версией во флоте",
      any(row["engine_version"] == _ENGINE and row["lease_contract"] == 3 for row in fleet),
      str([row for row in fleet if row["engine_version"] == _ENGINE]))
_expected_bar = sum(row["instances"] for row in fleet if row["engine_version"] == _ENGINE)
_metrics_text = admin.get("/admin/metrics", headers=ADMIN).text
check("метрика флота суммирует строки одной версии (по контрактам), а не берёт последнюю",
      f'pseudex_fleet_instances{{engine_version="{_ENGINE}"}} {_expected_bar}' in _metrics_text
      and _expected_bar >= 2,
      f"ожидалось {_expected_bar}: " + " | ".join(l for l in _metrics_text.splitlines() if "fleet_instances" in l))

# Отзыв отсутствием: реестр пропал — следующее продление стирает вердикт целиком.
server.REGISTRY = _registry.Watch("")
ladder._renew()
retracted = ladder.status()
check("без блока в ответе вердикт и уведомление отозваны, а не запомнены",
      retracted.latest is None and retracted.notice is None and retracted.deprecated_at is None
      and retracted.running_latest is None, str(retracted))

# D-064: формат бандла новее, чем понимает движок — «обновите», не «повреждён»;
# на продлении — grace (бандл остаётся загружен), на старте — терминальный код.
server.BUNDLE_FORMAT = 99
ladder._renew()
check("формат новее на продлении: бандл остаётся, ошибка названа форматом, не порчей",
      _ASSETS.is_loaded and "bundle_format 99" in (ladder.status().last_error or "")
      and ladder.status().code is None, str(ladder.status().last_error))
try:
    engine("ladder-cold", "start")
    cold_code = "no error"
except _LicenseError as error:
    cold_code = error.code
check("формат новее на старте: bundle_format_unsupported, не bundle_corrupt",
      cold_code == "bundle_format_unsupported", cold_code)
server.BUNDLE_FORMAT = 2

# 426 через клиент: вердикт вне grace — как 402/403.
_registry.dump(_relative_doc(eol=(_today - _dt.timedelta(days=1)).isoformat(),
                             announced=(_today - _dt.timedelta(days=100)).isoformat()), _reg_path)
server.REGISTRY = _registry.Watch(_reg_path)
ladder._renew()
refused_status = ladder.status()
check("426 на продлении — терминальный unsupported_client, словари выгружены, grace не применяется",
      refused_status.code == "unsupported_client" and refused_status.state == "expired"
      and not _ASSETS.is_loaded and "pseudexctl upgrade" in (refused_status.last_error or ""),
      f"code={refused_status.code} state={refused_status.state} loaded={_ASSETS.is_loaded}")
try:
    engine("ladder-refused", "start")
    refused_code = "no error"
except _LicenseError as error:
    refused_code = error.code
check("426 на старте — LicenseError unsupported_client с подсказкой обновиться",
      refused_code == "unsupported_client" and "pseudexctl upgrade" in explain("unsupported_client"),
      refused_code)
server.REGISTRY = _registry.Watch("")

print(f"\nсломано {len(fails)}")
raise SystemExit(1 if fails else 0)
