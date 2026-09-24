"""ПОТОЛОК ЗАПРОСОВ ПЕРИОДА на лицензионном сервере (docs/tz-license-volume-quota.md §C).

Написано ПО КОНТРАКТУ §4, а не под реализацию, и каждая проверка умеет
покраснеть. `test_metering_attacks.py` (строки 6–8) прямо оставляет проверку
самого потолка и овереджа автору тестов — это она.

Утверждается ровно то, что обещает §C и §4:

  * `/admin/ceiling` ХРАНИТ присланное число (и обновляет его);
  * `/v1/meter` ОТКАЗЫВАЕТ в новой ёмкости сверх потолка ЛЮБОМУ процессу —
    в том числе процессу, который НЕ прислал ни одного слот-поля и не брал
    аренды (анти-Б35: лазейки `binding is None` больше нет);
  * отказ МЯГКИЙ: код `ceiling_reached` вне `_ANSWER_CODES` выпущенного движка,
    а 409 внутри его `_GRACE_WORTHY_STATUS` — флот доцеживает купленную полосу,
    а не гаснет мгновенно (урок Б30);
  * `ceiling_requests = 0` (или отсутствие) — БЕЗ потолка: ёмкость выдаётся;
  * новый (поднятый) потолок СНИМАЕТ отказ.

Поднимается НАСТОЯЩИЙ `server.app`/`server.admin_app` через `TestClient` —
без двойников, ровно тот путь, которым ходят контейнер и витрина. Токены
выставляются ДО импорта: сервер читает их на импорте.

    cd prototype && python3 licensing/test_ceiling.py
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
from licensing.store import CEILING_REACHED  # noqa: E402
# Что движок считает ОТВЕТОМ (жёсткий стоп) и что — нашим сбоем (grace),
# читается из самого движка, а не переписывается сюда: копия жила бы своей
# жизнью до первой правки в `pseudex/license.py`.
from pseudex.license import _ANSWER_CODES, _GRACE_WORTHY_STATUS  # noqa: E402

public = TestClient(server.app)
admin = TestClient(server.admin_app)
ADMIN = {"Authorization": "Bearer test-admin"}
SHOP = {"Authorization": "Bearer test-shop"}

fails: list[str] = []


def check(name: str, held: bool, detail: str = "") -> None:
    print(f"  {'ДЕРЖИТ ' if held else 'СЛОМАНО'} {name}   {detail}")
    if not held:
        fails.append(name)


def issue(org: str, plan: str = "start") -> str:
    body = admin.post("/admin/issue", json={"org_id": org, "plan": plan},
                      headers=ADMIN)
    assert body.status_code == 200, body.text
    return body.json()["key"]


def set_ceiling(org: str, value: int) -> object:
    """Тем токеном, которым ходит витрина (`/admin/ceiling` открыт витрине)."""
    return admin.post("/admin/ceiling",
                      json={"org_id": org, "ceiling_requests": value},
                      headers=SHOP)


def meter(key: str, pubkey: str) -> object:
    """Купить квант ёмкости, назвав ТОЛЬКО ключ, ключ процесса и nonce.

    Ни slot, ни generation, ни instance_id — это и есть процесс «без полей
    слота» из §4 (анти-Б35): он не привязан ни к чему, и потолок обязан бить
    по нему так же, как по любому другому.
    """
    return public.post("/v1/meter",
                       json={"key": key, "pubkey": pubkey, "nonce": "n-" + pubkey})


# --- 1. /admin/ceiling ХРАНИТ ЧИСЛО -------------------------------------
print("ХРАНЕНИЕ ПОТОЛКА")
key = issue("ceilco")
resp = set_ceiling("ceilco", 100)
check("POST /admin/ceiling принят (200)", resp.status_code == 200, resp.text)
check("ответ несёт записанное число",
      resp.status_code == 200 and resp.json().get("ceiling_requests") == 100,
      resp.text)
check("сервер хранит потолок на организации",
      server.STORE.ceiling_of("ceilco")["ceiling_requests"] == 100,
      str(server.STORE.ceiling_of("ceilco")))

# Обновляемо (новый период → новое число), идемпотентно.
set_ceiling("ceilco", 250)
check("повторный POST обновляет потолок",
      server.STORE.ceiling_of("ceilco")["ceiling_requests"] == 250)
set_ceiling("ceilco", 100)   # вернуть для проверок ниже

# Нечисловое тело — 400, а не молчаливая запись мусора.
bad = admin.post("/admin/ceiling",
                 json={"org_id": "ceilco", "ceiling_requests": "lots"},
                 headers=SHOP)
check("нечисловой потолок отвергается (400)", bad.status_code == 400, bad.text)


# --- 2. /v1/meter ОТКАЗЫВАЕТ СВЕРХ ПОТОЛКА ЛЮБОМУ ПРОЦЕССУ ----------------
print("\nОТКАЗ СВЕРХ ПОТОЛКА (анти-Б35)")
# Процесс A выбирает потолок: первый грант зажимается числом 100.
a = meter(key, "procA")
check("процесс под потолком покупает ёмкость (200)",
      a.status_code == 200 and a.json().get("kind") == "capacity",
      f"{a.status_code} {a.text[:120]}")
check("организация упёрлась в потолок после выборки",
      server.STORE._org_granted("ceilco") >= 100,
      f"granted={server.STORE._org_granted('ceilco')}")

# Процесс B — ДРУГОЙ ключ процесса, НИ ОДНОГО слот-поля, аренды не брал.
b = meter(key, "procB")
check("новому процессу без полей слота отказано сверх потолка (409)",
      b.status_code == 409, f"{b.status_code} {b.text[:160]}")
check("тело отказа несёт код ceiling_reached",
      b.status_code == 409 and b.json().get("error") == CEILING_REACHED,
      b.text[:160])


# --- 3. ОТКАЗ МЯГКИЙ (урок Б30) ------------------------------------------
print("\nМЯГКОСТЬ ОТКАЗА")
check("код отказа (409) — grace-worthy для движка",
      409 in _GRACE_WORTHY_STATUS,
      f"_GRACE_WORTHY_STATUS={sorted(_GRACE_WORTHY_STATUS)}")
check("ceiling_reached НЕ в _ANSWER_CODES (не жёсткий стоп)",
      CEILING_REACHED not in _ANSWER_CODES,
      f"_ANSWER_CODES={sorted(_ANSWER_CODES)}")


# --- 4. ПОДНЯТЫЙ ПОТОЛОК СНИМАЕТ ОТКАЗ ------------------------------------
print("\nНОВЫЙ ПОТОЛОК СНИМАЕТ ОТКАЗ")
set_ceiling("ceilco", 10_000_000)
c = meter(key, "procC")   # свежий процесс, чтобы не поймать частотный 429
check("после подъёма потолка ёмкость снова выдаётся (200)",
      c.status_code == 200 and c.json().get("kind") == "capacity",
      f"{c.status_code} {c.text[:120]}")


# --- 5. ceiling = 0 — БЕЗ ПОТОЛКА ----------------------------------------
print("\nПОТОЛОК 0 = БЕЗ ПОТОЛКА")
free_key = issue("freeco")
set_ceiling("freeco", 0)
check("ceiling_of отдаёт 0 как «без потолка»",
      server.STORE.ceiling_of("freeco")["ceiling_requests"] == 0)
# Несколько РАЗНЫХ процессов, каждый покупает — ни одного 409.
statuses = [meter(free_key, f"free{i}").status_code for i in range(5)]
check("без потолка все процессы покупают ёмкость (ни одного 409)",
      all(code == 200 for code in statuses), f"коды={statuses}")

# И явное снятие ранее выставленного потолка (100 → 0) тоже покупает.
capped_key = issue("wasco")
set_ceiling("wasco", 100)
meter(capped_key, "w1")                       # выбрать потолок
blocked = meter(capped_key, "w2").status_code  # должен упереться
set_ceiling("wasco", 0)                        # снять потолок
freed = meter(capped_key, "w3").status_code    # теперь можно
check("снятие потолка в 0 снимает отказ",
      blocked == 409 and freed == 200,
      f"под потолком={blocked} после снятия={freed}")


# --- 6. ДРЕЙФ Σ(granted−billable) НЕ СЪЕДАЕТ КВОТУ (регрессия) ------------
# Потолок стоит на BILLABLE, а не на SUM(granted). Мёртвые процессы (рестарты,
# редеплои) оставляют строки с granted >> billable: грант несёт невыбранный
# резерв (до 48 ч трафика), а реальный расход мал. Если считать «занятое»
# грантом, замороженный резерв G=Σ(granted−billable) копится по флоту и при
# G≥included ОТКАЗЫВАЕТ платящему на ПЕРВОМ запросе свежего периода — недодача
# оплаченной квоты. Здесь это пиннится: свежий процесс покупает ёмкость, пока
# кумулятивный BILLABLE под потолком, и упирается ТОЛЬКО когда billable (а не
# сумма грантов) добирается до него.
print("\nДРЕЙФ РЕЗЕРВА НЕ СЪЕДАЕТ КВОТУ (billable, не SUM(granted))")
INCLUDED = 5000            # ceiling = watermark + included; берём как included
drift_key = issue("driftco")
set_ceiling("driftco", INCLUDED)


def seed_dead(pubkey: str, granted: int, acked: int,
              quantum_size: int, reserve: int) -> None:
    """Вписать МЁРТВУЮ строку ледджера прямо в `meter` — процесс, который брал
    ёмкость и не вернулся. `granted` велик (резерв), `acked` мал (реальный
    расход). Через /v1/meter такое не набрать одним запросом; строим ledger."""
    now = time.time()
    with server.STORE._lock:
        server.STORE._conn.execute(
            "INSERT OR REPLACE INTO meter (org_id, pubkey, first_seen, "
            "updated_at, quantum_seq, quantum_size, reserve, granted, "
            "prefetch_at, acked, acked_at, ack_trust, unacked_quanta) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("driftco", pubkey, now, now, 3, quantum_size, reserve, granted,
             0, acked, now, "signed", 0))
        server.STORE._conn.commit()


# 12 мёртвых процессов: granted 1000, но billable (=acked, зажатый полосой) 40.
# floor = max(0, 1000 − 200 − 2000) = 0 → billable_row = clamp(40, 0, 1000) = 40.
for i in range(12):
    seed_dead(f"dead{i}", granted=1000, acked=40, quantum_size=200, reserve=2000)

drift_granted = server.STORE._org_granted("driftco")
drift_billable = server.STORE.billable("driftco")["billable"]
check("замороженный резерв набран: SUM(granted) ≥ потолка",
      drift_granted >= INCLUDED,
      f"granted={drift_granted} ceiling={INCLUDED}")
check("а BILLABLE (реальный расход) ещё далеко под потолком",
      drift_billable < INCLUDED,
      f"billable={drift_billable} ceiling={INCLUDED}")
check("замороженный резерв G=Σ(granted−billable) ≥ included",
      drift_granted - drift_billable >= INCLUDED,
      f"G={drift_granted - drift_billable} included={INCLUDED}")

# ГЛАВНОЕ: свежий процесс ВСЁ РАВНО покупает ёмкость. На старом счёте
# (SUM(granted)=12000 ≥ 5000) он получил бы 409 — дрейф съел бы оплаченную
# квоту. На новом (billable=480 < 5000) — 200.
fresh = meter(drift_key, "driftFresh1")
check("свежий процесс покупает ёмкость, дрейф резерва не отказал (200)",
      fresh.status_code == 200 and fresh.json().get("kind") == "capacity",
      f"{fresh.status_code} {fresh.text[:160]}")

# Теперь поднимаем BILLABLE до потолка настоящим расходом (acked велик, полоса
# узкая): floor = max(0, 1000 − 200 − 100) = 700 → billable_row = 1000.
for i in range(5):
    seed_dead(f"real{i}", granted=1000, acked=1000, quantum_size=200, reserve=100)

drift_billable2 = server.STORE.billable("driftco")["billable"]
check("BILLABLE добрался до потолка настоящим расходом",
      drift_billable2 >= INCLUDED,
      f"billable={drift_billable2} ceiling={INCLUDED}")
blocked = meter(drift_key, "driftFresh2")
check("отказ наступает ТОЛЬКО когда BILLABLE достиг потолка (409)",
      blocked.status_code == 409
      and blocked.json().get("error") == CEILING_REACHED,
      f"{blocked.status_code} {blocked.text[:160]}")


print("=" * 64)
if fails:
    print(f"ПОТОЛОК СЛОМАН: {len(fails)} проверок красные")
    for name in fails:
        print(f"  - {name}")
    raise SystemExit(1)
print("ПОТОЛОК ЗАПРОСОВ ПЕРИОДА держит контракт §C/§4 целиком")
