"""КЛИЕНТСКАЯ ПОЛОВИНА СЛОТОВ И ПОКОЛЕНИЙ — ПРОТИВ НАСТОЯЩЕГО СЕРВЕРА.

    cd prototype && python3 test_slots_client.py

ПОЧЕМУ ЗДЕСЬ НАСТОЯЩИЙ `uvicorn`, А НЕ ПОДМЕНЁННЫЙ `httpx`. Проверяемое
свойство — «перезапуск не заводит нового места» — живёт РОВНО в стыке клиента и
сервера: клиент называет старт, сервер решает по установке, оба пишут в одну
таблицу. Двойник любой из половин проверяет собственную копию этого решения, и
шесть заходов подряд ломались именно там, где копия расходилась с оригиналом
(Б26 … Б26sexies). `TestClient` тоже не годится: он не даёт клиенту сетевого
адреса, а `LicenseClient` ходит по HTTP и никак иначе.

ЧТО ИМЕННО ЗДЕСЬ КРАСНЕЕТ, ЕСЛИ КОД ВЕРНУТЬ НАЗАД:

  * перезапуск, забирающий НОВОЕ место (сегодняшний 0.3.17 отказывал на 6-м,
    9-м и 3-м честном старте — Б26sexies);
  * OOM, отличимый от `docker stop` хоть одним полем, читаемым решением: тогда
    «попрощаться нечем» снова становится наказуемым;
  * Б30 — отказ в НОВОЙ ёмкости, гасящий процесс немедленно и сжигающий
    оплаченный остаток;
  * N воркеров одного старта, ставшие N поколениями и отфенсившие друг друга.
"""

import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("PSEUDEX_LICENSE_DB", tempfile.mktemp(suffix=".db"))
os.environ["PSEUDEX_LICENSE_ADMIN_TOKEN"] = "test-admin"
os.environ["PSEUDEX_LICENSE_STOREFRONT_TOKEN"] = "test-shop"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from licensing import server  # noqa: E402
from pseudex.assets import ASSETS  # noqa: E402
from pseudex.bundle import sign_lease  # noqa: E402
# Константы читаются ИЗ ДВИЖКА, а не переписываются сюда: копия живёт своей
# жизнью ровно до первой правки в `pseudex/license.py`.
from pseudex.license import (  # noqa: E402
    FENCED, STATE_LEASED, Fenced, LicenseClient, LicenseError, block_code,
    explain_fenced, should_reclaim, start_id, _RECLAIM_MIN_INTERVAL_SECONDS)
from pseudex.operator import slot_state  # noqa: E402

fails: list[str] = []


def check(name: str, held: bool, detail: str = "") -> None:
    print(f"  {'ДЕРЖИТ ' if held else 'СЛОМАНО'} {name}   {detail}")
    if not held:
        fails.append(name)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


_port = _free_port()
_serving = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=_port,
                                         log_level="error"))
threading.Thread(target=_serving.run, daemon=True).start()
BASE = f"http://127.0.0.1:{_port}"
for _ in range(200):
    try:
        httpx.get(f"{BASE}/health", timeout=1)
        break
    except httpx.HTTPError:
        time.sleep(0.05)

os.environ["PSEUDEX_LICENSE_PUBKEY"] = server.PUBLIC_KEY


def client(key: str, installation: str, start: str) -> LicenseClient:
    """Настоящий движок: свой ключ процесса, свой старт, свой том."""
    os.environ["PSEUDEX_START_ID"] = start
    return LicenseClient(
        base_url=BASE, key=key, instance_id=installation, ca_path="",
        usage_provider=lambda: {"requests": 0, "entities": {}, "values": 0})


def started(key: str, installation: str, start: str) -> LicenseClient:
    engine = client(key, installation, start)
    engine.acquire()
    return engine


def slots(org: str) -> dict:
    return server.STORE.slots_view(org, server.STORE.org_plan(org),
                                   server._TTL_SECONDS, time.time())


# --- СТАРТ — ЭТО ПОКОЛЕНИЕ, И ОНО ОДНО НА ВСЕХ ВОРКЕРОВ ------------------
print("СТАРТ КОНТЕЙНЕРА")
os.environ["PSEUDEX_START_ID"] = "S-declared"
check("объявленный старт побеждает вывод", start_id("inst") == "S-declared")
os.environ["PSEUDEX_START_ID"] = "x" * 300
check("длинное значение режется до 128 байт", len(start_id("inst")) == 128,
      f"длина {len(start_id('inst'))}")
os.environ["PSEUDEX_START_ID"] = "S-one"
check("два воркера одного старта — ОДНО значение",
      start_id("inst") == start_id("inst"),
      "иначе N воркеров стали бы N поколениями на одном слоте")

key_one = server.STORE.issue_key("slots-one", "start")
workers = [started(key_one, "vol-A", "S-1") for _ in range(3)]
view = slots("slots-one")
check("три воркера одного старта заняли ОДНО место",
      view["occupied"] == 1 and view["generations_24h"] == 1,
      f"занято {view['occupied']}, поколений {view['generations_24h']}")
check("и все трое получили один слот и один эпох",
      {(w.status().slot_no, w.status().epoch) for w in workers} == {(1, 1)},
      f"{sorted({(w.status().slot_no, w.status().epoch) for w in workers})}")
check("тариф назвал число мест", workers[0].status().slot_count == 1,
      f"slot_count {workers[0].status().slot_count}")


# --- ПЕРЕЗАПУСК НЕ ЗАВОДИТ НОВОГО МЕСТА ----------------------------------
print("\nДЕСЯТЬ ПЕРЕЗАПУСКОВ ПОДРЯД")
key_restart = server.STORE.issue_key("slots-restart", "start")
epochs = []
for run in range(1, 11):
    engine = started(key_restart, "vol-R", f"S-run-{run}")
    epochs.append((engine.status().slot_no, engine.status().epoch))
view = slots("slots-restart")
check("каждый перезапуск — тот же слот и следующее поколение",
      epochs == [(1, n) for n in range(1, 11)], f"{epochs}")
check("мест по-прежнему одно, занято одно",
      view["slot_count"] == 1 and view["occupied"] == 1,
      "выпущенный 0.3.17 на этом сценарии отказывал на 6-м, 9-м и 3-м старте")
check("поколений за сутки — десять, и это НАША запись",
      view["generations_24h"] == 10, f"{view['generations_24h']}")


# --- OOM НЕОТЛИЧИМ ОТ ОБЫЧНОГО ПЕРЕЗАПУСКА -------------------------------
print("\nOOM = ПЕРЕЗАПУСК")


def restart_cycle(org: str, say_goodbye: bool) -> dict:
    """Один код с флагом «звать /v1/release или нет» — иначе сравнивались бы
    два разных кода, а не два поведения сервера."""
    key = server.STORE.issue_key(org, "start")
    first = started(key, f"vol-{org}", "S-before")
    if say_goodbye:
        first.stop()          # docker stop: воркеры прощаются
    # SIGKILL: прощаться нечем, процесс просто исчезает.
    started(key, f"vol-{org}", "S-after")
    return slots(org)


polite = restart_cycle("slots-stop", True)
killed = restart_cycle("slots-oom", False)


def decided(view: dict) -> dict:
    """Только то, что читает РЕШЕНИЕ. `released_at` и имена организаций из
    сравнения исключены намеренно: первое — история для экрана, второе
    различается по построению."""
    slot = view["slots"][0]
    holder = slot["holder"] or {}
    return {"occupied": view["occupied"], "slot_count": view["slot_count"],
            "epoch": slot["epoch"], "start_id": holder.get("start_id"),
            "draining": [d["epoch"] for d in slot["draining"]],
            "generations_24h": view["generations_24h"]}


check("записи сервера после SIGKILL и после docker stop совпадают",
      decided(polite) == decided(killed),
      f"{decided(polite)} vs {decided(killed)}")
check("и обе — второе поколение своего слота",
      decided(killed)["epoch"] == 2, f"эпох {decided(killed)['epoch']}")
def goodbye_recorded(org: str) -> bool:
    rows = server.STORE._fetchall(
        "SELECT released_at FROM generations WHERE org_id=? AND start_id=?",
        (org, "S-before"))
    return bool(rows) and rows[0][0] is not None


check("прощание ЗАПИСАНО, когда оно было",
      goodbye_recorded("slots-stop"), "иначе экран не скажет «остановлен сам»")
check("и его отсутствие после SIGKILL тоже записано честно",
      not goodbye_recorded("slots-oom"),
      "две записи различаются только историей — ни одно решение её не читает")


# --- Б30: ОТКАЗ В НОВОЙ ЁМКОСТИ НЕ ГАСИТ ПРОЦЕСС -------------------------
print("\nБ30: ФЕНСИНГ ДОЦЕЖИВАЕТ, А НЕ ГАСИТ")
key_fence = server.STORE.issue_key("slots-fence", "start")
older = started(key_fence, "vol-old", "S-older")
consumed_before, granted_before = older.capacity()
newer = started(key_fence, "vol-new", "S-newer")
check("чужая установка взяла единственный слот, аренде ответили 200",
      newer.status().epoch == 2 and newer.status().slot_no == 1,
      f"слот {newer.status().slot_no}, эпох {newer.status().epoch}")

time.sleep(1.1)   # потолок частоты на ручке — один квант в секунду на ключ
older._meter_step()
status = older.status()
check("отфенсенный НЕ получил терминального кода",
      status.code is None, f"код {status.code}")
check("его аренда осталась активной", status.state == STATE_LEASED, status.state)
check("словари детекции НЕ выгружены — это и есть Б30",
      ASSETS.is_loaded,
      "раньше та же ветка звала _expire(), и /mask отдавал 503 в ту же секунду")
check("он всё ещё обслуживает уже купленное", older.is_serving(),
      f"куплено {granted_before}, потрачено {consumed_before}")
check("и больше не покупает", not older._quantum_due(),
      "покупка при чужом эпохе получила бы тот же отказ")
check("состояние названо словом, а не выведено из полей",
      slot_state(status)["state"] == "fenced", str(slot_state(status)["state"]))
check("сервер назвал, КТО занял место",
      status.fenced["current_epoch"] == 2, str(status.fenced))
check("и это едет в текст для оператора",
      "поколение 2" in explain_fenced(status.fenced),
      explain_fenced(status.fenced)[:80])

# ПОЛОСА КОНЧИЛАСЬ — ВОТ ТЕПЕРЬ ОСТАНОВКА, И ЕЁ СДЕЛАЛА has_capacity().
consumed, granted = older.capacity()
for _ in range(granted - consumed):
    older.consume()
check("купленное кончилось — гасит обычная проверка ёмкости",
      not older.is_serving(), f"{older.capacity()}")
check("и 503 несёт код fenced, а не capacity_exhausted",
      block_code(older.status()) == FENCED, block_code(older.status()))


# --- ПЕРЕЗАЯВКА: ОДНА, И НЕ ЧАЩЕ РАЗА В ЧАС ------------------------------
print("\nПЕРЕЗАЯВКА")
check("сразу после фенсинга она назначена",
      older._reclaim_at is not None and older._last_reclaim_monotonic is None)
check("правило допуска пускает первую",
      should_reclaim(older._reclaim_at, older._last_reclaim_monotonic,
                     older._last_reclaim_attempt_monotonic, 0,
                     older._reclaim_at + 0.1))

# СОРВАВШАЯСЯ ПОПЫТКА НЕ ТРАТИТ ПЕРЕЗАЯВКУ. Без этого секунда без связи ровно
# в момент возврата стоит клиенту часа темноты — в том числе живому соседу,
# ошибочно вытесненному ранжированием, ради которого перезаявка и заведена.
_real_base, older._base_url = older._base_url, "http://127.0.0.1:1"
older._reclaim_step()
older._base_url = _real_base
check("перезаявка, не дошедшая до сервера, не потрачена",
      older._last_reclaim_monotonic is None and older._fenced is not None,
      f"потрачена={older._last_reclaim_monotonic is not None}")
check("но и не повторяется каждый тик",
      not should_reclaim(older._reclaim_at, older._last_reclaim_monotonic,
                         older._last_reclaim_attempt_monotonic, 0,
                         time.monotonic()))
older._last_reclaim_attempt_monotonic = None

older._reclaim_step()
check("перезаявка взяла слот новым поколением",
      older.status().epoch == 3 and older._fenced is None,
      f"эпох {older.status().epoch}, fenced={older._fenced}")
check("и покупки возобновились", older._quantum_due())
check("вторая сразу — НЕ делается",
      not should_reclaim(older._reclaim_at, older._last_reclaim_monotonic,
                         older._last_reclaim_attempt_monotonic, 0,
                         time.monotonic()))
# ВАРИАНТ А: ТЁМНЫЙ ЖДЁТ МИНУТУ, ОБСЛУЖИВАЮЩИЙ — ЧАС. Час — пол против двух
# ЖИВЫХ контейнеров; процесс с исчерпанной полосой уже отдаёт 503, и держать
# его час значило бы выдать вариант Б за вариант А (§6.1 ТЗ).
_spent = time.monotonic()
check("тёмный (полоса кончилась) возвращается через минуту, а не через час",
      should_reclaim(None, _spent, None, 0, _spent + 61.0)
      and not should_reclaim(None, _spent, None, 0, _spent + 30.0))
check("обслуживающий (полоса есть) — не чаще раза в час",
      not should_reclaim(_spent, _spent, None, 200, _spent + 61.0)
      and should_reclaim(_spent, _spent, None, 200,
                         _spent + _RECLAIM_MIN_INTERVAL_SECONDS + 1.0))

time.sleep(1.1)
newer._meter_step()
check("теперь отфенсен тот, кто держал: они чередуются, а не запирают друг друга",
      newer._fenced is not None and newer.is_serving(),
      f"fenced={newer._fenced is not None}, обслуживает={newer.is_serving()}")


# --- ТЕГ (СЛОТ, ЭПОХ) ДОЕХАЛ ДО ЛЕДЖЕРА ----------------------------------
print("\nТЕГ ЛЕДЖЕРА")
tagged = server.STORE._fetchall(
    "SELECT slot_no, epoch FROM meter WHERE org_id=? AND slot_no IS NOT NULL",
    ("slots-fence",))
check("каждая покупка помечена слотом и поколением", bool(tagged), str(tagged))
check("и ни одна не помечена поколением НОВЕЕ текущего",
      all(int(epoch) <= slots("slots-fence")["slots"][0]["epoch"] for _, epoch in tagged),
      str(tagged))


# --- СТАРЫЙ СЕРВЕР: ПОЛЕЙ НЕТ, И ДВИЖОК НЕ ВСТАЁТ ------------------------
print("\nСТАРЫЙ СЕРВЕР")
# Настоящая аренда настоящего сервера, у которой СНЯТЫ новые поля и заново
# поставлена подпись НАСТОЯЩИМ ключом: ровно то, что отдаёт сервер, который
# про слоты не знает. Это не двойник — это тот же код и та же подпись.
key_old = server.STORE.issue_key("slots-old", "start")
legacy = client(key_old, "vol-legacy", "S-legacy")
raw = legacy._request_lease()
for field in ("slot_no", "epoch", "slot_count", "signature"):
    raw.pop(field, None)
raw["signature"] = sign_lease(raw, server.SIGNING_KEY)
legacy._apply(raw)
check("аренда без слота принята — движок не требует полей",
      legacy.status().slot_no is None and legacy.state() == STATE_LEASED,
      "иначе это второй recipient-дефект: движок, вставший из-за порядка выкатки")
check("экран говорит «неизвестно», а не «слот 1»",
      slot_state(legacy.status())["state"] == "unknown",
      str(slot_state(legacy.status())["state"]))
legacy._meter_once()
check("и ёмкость покупается как раньше", legacy.capacity()[1] > 0,
      f"{legacy.capacity()}")


# --- ДИАГНОЗ 503: ТРИ РАЗНЫХ, А НЕ ОДИН ----------------------------------
print("\nДИАГНОЗ 503")
# Аренда взята, первый квант НЕ куплен: слот успел занять ещё более новый
# запуск. Это единственное состояние, в котором `granted` равен нулю у
# работающего движка, и раньше оно читалось как «лицензия истекла».
cold = client(server.STORE.issue_key("slots-cold", "start"), "vol-cold", "S-cold")
cold._apply(cold._request_lease())
cold._enter_fenced(Fenced(slot_no=1, epoch=1, current_epoch=2,
                          holder_start_id="S-x", holder_since=None,
                          detail="", since=time.time()))
check("отфенсенный ДО первой покупки — это fenced, а не «лицензия истекла»",
      block_code(cold.status()) == FENCED, block_code(cold.status()))
check("ёмкости у него нет вовсе, и это не мешает диагнозу",
      cold.capacity() == (0, 0), str(cold.capacity()))


# --- РАСКАТКА K8S: ФЕНСИНГ СНИМАЕТ ОТВЕТ СЕРВЕРА, А НЕ СВОЙ НОМЕР ---------
print("\nРАСКАТКА K8S")
# Однорепличный Deployment удваивается при КАЖДОЙ раскатке (maxUnavailable 25%
# округляется вниз до 0, maxSurge вверх до 1), поэтому два пода на одном PVC —
# не редкость, а каждый выкат клиента. Воркеров у пода несколько, перезаявляет
# слот один из них, и остальные узнают об этом только от сервера.
key_roll = server.STORE.issue_key("slots-roll", "start")
old_pod = [started(key_roll, "pvc", "S-pod-old") for _ in range(2)]
new_pod = [started(key_roll, "pvc", "S-pod-new") for _ in range(2)]
check("новый под встал на ТОТ ЖЕ слот той же установки",
      {(w.status().slot_no, w.status().epoch) for w in new_pod} == {(1, 2)},
      f"{sorted({(w.status().slot_no, w.status().epoch) for w in new_pod})}")

time.sleep(1.1)
for worker in old_pod:
    worker._meter_step()
check("оба воркера старого пода отфенсены",
      all(w._fenced is not None for w in old_pod))

old_pod[0]._reclaim_step()
check("перезаявка ОДНОГО воркера вернула слот ВСЕМУ поколению",
      old_pod[0].status().epoch == 3 and old_pod[0]._fenced is None,
      f"эпох {old_pod[0].status().epoch}")

# БРАТ ПО СТАРТУ. Его аренда по-прежнему привязана к эпоху 1, его память — тоже,
# но сервер судит ПОКОЛЕНИЕ, и поколение держит слот. Значит на его покупку
# сервер отвечает «да».
time.sleep(1.1)
granted_before = old_pod[1].capacity()[1]
old_pod[1]._meter_step()
check("сервер ВЫДАЛ брату квант — фенсинга на нём нет",
      old_pod[1].capacity()[1] > granted_before,
      f"было {granted_before}, стало {old_pod[1].capacity()[1]}")
check("и клиент принял этот ответ: FENCED снят",
      old_pod[1]._fenced is None,
      "правило «снимать только при СМЕНЕ эпоха» держало брата отфенсенным "
      "навсегда: _quantum_due() при _fenced возвращает False, покупок нет, "
      "полоса дотекает, контейнер темнеет, ДЕРЖА слот")

# ДЕРЖАТЕЛЬ — ОН САМ. Такую форму отказа сервер выдаёт на выведенный тарифом
# слот (`_fence_detail`, ветка `retired`): поколение держит слот, эпохи равны,
# `holder_start_id` — этот же старт. Сравнение номеров не может её снять НИКОГДА,
# и это не теория: ровно этим отфенсенный воркер нового пода запирал сам себя.
held = old_pod[1].status()
old_pod[1]._enter_fenced(Fenced(
    slot_no=held.slot_no, epoch=held.epoch, current_epoch=held.epoch,
    holder_start_id=old_pod[1]._start_id, holder_since=time.time(),
    detail="слот выведен сменой тарифа", since=time.time()))
check("отфенсенный СВОИМ ЖЕ поколением — тоже отфенсенный",
      old_pod[1]._fenced is not None)
old_pod[1]._clear_fencing("аренда")
check("и ответ сервера снимает его, хотя номер поколения не менялся",
      old_pod[1]._fenced is None,
      "иначе воркер заперт: перезаявка вернёт тот же эпох, потому что держатель "
      "— он сам, и сравнение номеров не снимет фенсинг ни на одной итерации")


# --- ХОЛОДНЫЙ СТАРТ, ОТФЕНСЕННЫЙ НА ПЕРВОМ КВАНТЕ ------------------------
print("\nХОЛОДНЫЙ СТАРТ ПРОТИВ ЗАНЯТОГО СЛОТА")
key_cold2 = server.STORE.issue_key("slots-race", "start")


neighbour = client(key_cold2, "vol-race-other", "S-race-other")


class RacedStart(LicenseClient):
    """Слот увели МЕЖДУ арендой и первым квантом — ровно то, что делает старый
    под, перезаявляющий слот, пока новый поднимается.

    Двойника здесь нет: обе половины отвечает настоящий сервер, и сосед берёт
    НАСТОЯЩУЮ аренду — заявка и есть то, что вытесняет. Тест выбирает только
    МОМЕНТ, потому что иначе это гонка, а гонка, краснеющая через раз, не
    проверка.
    """

    raced = False

    def _request_lease(self) -> dict:
        lease = super()._request_lease()
        if not RacedStart.raced:
            RacedStart.raced = True
            neighbour._apply(neighbour._request_lease())
        return lease


os.environ["PSEUDEX_START_ID"] = "S-race-mine"
raced = RacedStart(
    base_url=BASE, key=key_cold2, instance_id="vol-race-mine", ca_path="",
    usage_provider=lambda: {"requests": 0, "entities": {}, "values": 0})
raced.acquire()
check("сосед действительно занял слот, пока этот брал аренду",
      neighbour.status().epoch == raced.status().epoch + 1,
      f"сосед на {neighbour.status().epoch}, этот на {raced.status().epoch}")
check("вытесненный в этом окне контейнер ПОДНЯЛСЯ И ОБСЛУЖИВАЕТ",
      raced.state() == STATE_LEASED and ASSETS.is_loaded and raced.is_serving(),
      "сервер продаёт ПЕРВЫЙ квант процесса даже за фенсинг (store.py, "
      "`_never_granted`): вердикт, прилетевший между арендой и первой покупкой, "
      "иначе запирал бы клиента новой дверью — по одному разу на каждую "
      "раскатку K8s")
check("и клиент не изобрёл фенсинга, которого сервер не объявил",
      raced._fenced is None and raced.status().code is None,
      f"fenced={raced._fenced is not None}, код {raced.status().code}")


# --- ТЁМНЫЙ ОТФЕНСЕННЫЙ ВОЗВРАЩАЕТСЯ ЗА ОДИН ПРОХОД ПЕТЛИ -----------------
print("\nОДИН ПРОХОД: ПЕРЕЗАЯВИТЬ И КУПИТЬ")
# Полоса у него уже израсходована — он НЕ доцеживает, он отдаёт 503. Здесь
# порядок внутри прохода и есть вся разница: покупка перед перезаявкой означает,
# что снятый фенсинг ждёт СЛЕДУЮЩЕГО прохода — до пяти секунд простоя тому, кто
# уже не обслуживает. Секундный опрос холодного старта сюда не применим:
# квант он покупал, `_quantum_seq` не ноль.
key_dark = server.STORE.issue_key("slots-dark", "start")
dark = started(key_dark, "vol-dark", "S-dark")
started(key_dark, "vol-dark-other", "S-dark-other")
time.sleep(1.1)
dark._meter_step()
check("тёмный кандидат отфенсен и полоса у него ещё есть",
      dark._fenced is not None and dark.is_serving())
_c, _g = dark.capacity()
for _ in range(_g - _c):
    dark.consume()
check("а теперь полосы нет", not dark.is_serving(), str(dark.capacity()))
# Отметки перезаявки сбрасываются: правило допуска проверено отдельно (выше),
# здесь проверяется ПОРЯДОК прохода, а не пол частоты.
dark._last_reclaim_attempt_monotonic = None
dark._last_reclaim_monotonic = None
time.sleep(1.1)
dark.start()
_deadline = time.monotonic() + 2.0
while time.monotonic() < _deadline and not dark.is_serving():
    time.sleep(0.05)
check("один проход петли вернул слот И купил ёмкость",
      dark.is_serving() and dark._fenced is None,
      f"ёмкость {dark.capacity()}; при обратном порядке покупка ждала бы "
      f"следующего прохода — до пяти секунд 503 у процесса, которому нечего "
      f"доцеживать")
dark.stop()

# --- НОВЫЙ КЛИЕНТ ПРОТИВ СТАРОГО СЕРВЕРА (§7.2) --------------------------
print("\nСТАРЫЙ СЕРВЕР ОТКАЗЫВАЕТ В ПЕРВОМ КВАНТЕ")
# Стенд — НАСТОЯЩИЙ HTTP: всё, кроме `/v1/meter`, уходит настоящему серверу
# дословно, а `/v1/meter` отвечает тем, чем отвечал сервер ДО этого захода
# (`git show HEAD:licensing/server.py`, ветка `instance_limit`). Подменён не
# клиент и не транспорт, а одна ручка одного сервера — иначе «новый движок
# против старого сервера» пришлось бы поднимать из git-архива целиком, а
# изменилась в нём ровно эта ручка.
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402

legacy_app = FastAPI()


@legacy_app.post("/v1/meter")
async def legacy_meter(request: Request) -> JSONResponse:
    return JSONResponse({"error": "instance_limit",
                         "detail": "мест по тарифу больше нет"}, status_code=409)


@legacy_app.api_route("/{path:path}", methods=["GET", "POST"])
async def legacy_forward(request: Request, path: str) -> Response:
    upstream = httpx.request(request.method, f"{BASE}/{path}",
                             content=await request.body(),
                             headers={"content-type": "application/json"},
                             timeout=30)
    return Response(upstream.content, status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type"))


_legacy_port = _free_port()
_legacy = uvicorn.Server(uvicorn.Config(legacy_app, host="127.0.0.1",
                                        port=_legacy_port, log_level="error"))
threading.Thread(target=_legacy.run, daemon=True).start()
LEGACY = f"http://127.0.0.1:{_legacy_port}"
for _ in range(200):
    try:
        httpx.get(f"{LEGACY}/health", timeout=1)
        break
    except httpx.HTTPError:
        time.sleep(0.05)

os.environ["PSEUDEX_START_ID"] = "S-legacy-server"
against_old = LicenseClient(
    base_url=LEGACY, key=server.STORE.issue_key("slots-legacy-srv", "start"),
    instance_id="vol-legacy-srv", ca_path="",
    usage_provider=lambda: {"requests": 0, "entities": {}, "values": 0})
against_old.acquire()
check("отказ старого сервера в ПЕРВОМ кванте не мешает контейнеру встать",
      against_old.state() == STATE_LEASED,
      "instance_limit ловился только в петле, а на старте поднимался как "
      "терминальная ошибка лицензии — и движок не вставал против сервера, "
      "который ТЗ велит выкатывать первым (§7.3)")
check("и это «больше не покупаю», а не «умри»",
      against_old._fenced is not None and against_old.status().code is None,
      f"код {against_old.status().code}")
# У него `granted` ноль — состояние, которого против НОВОГО сервера не бывает
# (первый квант продаётся и за фенсинг), и единственное, где ноль ёмкости
# означает не «лицензия истекла», а «мест по тарифу нет».
check("и его 503 называет потолок, а не истёкшую лицензию",
      not against_old.is_serving() and block_code(against_old.status()) == FENCED,
      f"ёмкость {against_old.capacity()}, код {block_code(against_old.status())}")
check("классификация отказа по потолку — ОДНА на старт и на петлю",
      against_old.absorb_ceiling_refusal(
          LicenseError("instance_limit", "мест по тарифу больше нет"))
      and not against_old.absorb_ceiling_refusal(
          LicenseError("unpaid", "подписка не оплачена")),
      "ответ о подписке потолком не притворяется")

print()
if fails:
    print(f"СЛОМАНО {len(fails)}:")
    for name in fails:
        print(f"  - {name}")
    raise SystemExit(1)
print("слоты и поколения: перезапуск бесплатен, OOM неотличим, "
      "отказ в ёмкости доцеживает.")
