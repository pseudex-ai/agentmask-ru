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
# сливались с нулями, и `known_plan` такой тариф признавал: `may_lease` считал
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
        server.STORE.lease_if_allowed(
            f"ls_metric_{_renewal}_{_worker}", "fleet-org", "start",
            "fleet-inst", _worker, 86400, pubkey=_worker)
fleet = server.STORE.fleet_totals(86400)
check("шесть строк аренды — это один контейнер и два воркера",
      fleet["instances_serving"] >= 1 and fleet["processes_serving"] >= 2,
      f"организаций={fleet['orgs_serving']} контейнеров={fleet['instances_serving']} "
      f"воркеров={fleet['processes_serving']}")
_by_pubkey = server.STORE.fleet_totals(86400)["processes_serving"]
for _renewal in range(3, 6):
    server.STORE.lease_if_allowed(
        f"ls_metric_{_renewal}", "fleet-org", "start", "fleet-inst",
        "age1metric-a", 86400, pubkey="age1metric-a")
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

print(f"\nсломано {len(fails)}")
raise SystemExit(1 if fails else 0)
