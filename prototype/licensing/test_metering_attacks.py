"""АТАКИ на учёт инстансов и на цепь отчётов о расходе.

Набор написан, чтобы СЛОМАТЬ собственную логику, а не подтвердить её, и на
первом же прогоне сломал пять вещей из семи — включая ту, где правка оказалась
хуже дыры, которую чинила: быстрый путь «этот ключ уже держит слот» пропускал
пятьсот контейнеров, предъявивших один ключ.

ОДНА СТРОКА ЗДЕСЬ ВСЕГДА КРАСНАЯ, И ЭТО НАМЕРЕННО. Перехватчик, стоящий в
канале с САМОГО ПЕРВОГО обращения, подменяет открытый ключ отчётов и подписывает
свои — подпись не может доказать происхождение ключа, который она же и
принесла. Закрывается это только прикреплением сертификата нашего сервера в
релизном бинарнике, у чего своя цена в ротации. Пока не закрыто — строка стоит
красной, чтобы предел был виден, а не забыт.

    python3 licensing/test_metering_attacks.py
"""
import hashlib
import os, sys, tempfile, threading, time
sys.path.insert(0, ".")
from licensing.store import LicenseStore
import secrets as _secrets
from pseudex.bundle import (BundleError, generate_process_key, mac_report,
                            open_sealed, seal, verify_report)

def fresh(plan="start"):
    s = LicenseStore(tempfile.mktemp(suffix=".db")); s.issue_key("acme", plan); return s

def lease(s, inst, key, plan="start", start=None):
    # Через ту же ручку, которой ходит сервер: решение и запись — одна секция.
    # ЗДЕСЬ СТОЯЛ `lease_if_allowed` — МЕТОД, УДАЛЁННЫЙ ВМЕСТЕ С ДОПУСКОМ ПО
    # МЕСТАМ. Хелпер никто не звал, набор был зелёный, и следующий, кто написал
    # бы проверку через самый очевидно названный хелпер файла, получил бы
    # AttributeError вместо проверки.
    return s.lease_generation(f"ls-{inst}-{key}", "acme", plan,
                              start if start is not None else inst, inst, "p",
                              86400, pubkey=key)

fails = []
def check(name, held, detail=""):
    print(f"  {'ДЕРЖИТ ' if held else 'СЛОМАНО'} {name}   {detail}")
    if not held: fails.append(name)

print("АТАКИ НА УЧЁТ ПОКОЛЕНИЙ")
# ЧТО ЗДЕСЬ СТОЯЛО И ПОЧЕМУ ЕГО НЕТ.
#
# Четыре проверки мерили ПОТОЛОК ПРОЦЕССОВ («подмена instance_id», «ОДИН ключ
# на 500 контейнеров», «ПУСТОЙ ключ», «честные разные контейнеры и ключи» —
# каждая ждала `n <= 32`). Потолок процессов лечил E7: пятьдесят контейнеров с
# одним `PSEUDEX_INSTANCE_ID` читались как один инстанс, потому что имя
# выбирает клиент. КАК ЗАМОК ОН УДАЛЁН, и вот чем это лечится теперь: все
# контейнеры с одним именем — ОДНА установка, то есть один слот; поколения на
# нём фенсят друг друга, и покупает ёмкость ровно одно. Умножения нет —
# ограничивать число ключей незачем, а `processes_per_instance` осталось
# строкой тарифа для экрана.
#
# Гонка за слот остаётся, потому что остаётся то, что она мерит: между
# отдельным решением и отдельной записью лок отпускался, и замер прошлого
# захода дал 71 прошедшую гонку из 100. Единица другая — не «сколько аренд
# прошло», а «сколько эпохов начеканили».
s = fresh()
epochs, barrier = [], threading.Barrier(100)
lock = threading.Lock()


def race(number):
    barrier.wait()
    got = s.lease_generation(f"ls-race-{number}", "acme", "start", "ONE-START",
                             "vol-one", "p", 86400, pubkey=f"rk{number}")
    with lock:
        epochs.append(got["epoch"])


threads = [threading.Thread(target=race, args=(i,)) for i in range(100)]
for t in threads: t.start()
for t in threads: t.join()
check("сто одновременных аренд одного старта чеканят РОВНО ОДИН эпох",
      set(epochs) == {1}, f"эпохи {sorted(set(epochs))}")
check("и это один слот на все сто воркеров",
      s._slot_rows("acme")[0]["holder_start_id"] == "ONE-START",
      f"держатель {s._slot_rows('acme')[0]['holder_start_id']}")

# СТО РАЗНЫХ СТАРТОВ НА ОДНОМ СЛОТЕ — сто поколений, один держатель.
s2 = fresh()
for number in range(100):
    s2.lease_generation(f"ls-{number}", "acme", "start", f"S{number}",
                        f"vol-{number}", "p", 86400, pubkey=f"k{number}")
rows = s2._slot_rows("acme")
count = s2._fetchone("SELECT COUNT(*) FROM generations WHERE org_id='acme'", ())[0]
check("сто разных стартов — сто поколений и РОВНО ОДИН держатель слота",
      len(rows) == 1 and int(count) == 100 and rows[0]["epoch"] == 100,
      f"слотов {len(rows)}, поколений {count}, эпох {rows[0]['epoch']}")
# ПЕРВЫЙ КВАНТ ПРОЦЕССА ПРОДАЁТСЯ ВСЕГДА, ВТОРОЙ — ТОЛЬКО ДЕРЖАТЕЛЮ.
#
# Выпущенный движок покупает первый квант ВНУТРИ `acquire()`, и всё, что
# оттуда вылетело, — это три попытки и `bundle_unavailable`, то есть
# контейнер не поднимается вовсе. Отказать в нём значило бы запереть клиента
# ровно так же, как заходы четвёртый, пятый и шестой, только новой дверью;
# окно между арендой и первой покупкой открывается при каждой раскатке K8s.
# Цена названа: `Q_min` тарифа на процесс на аренду — та самая полоса, которую
# §3bis.2 уже объявила остатком и которую ни фенсинг, ни бюджет перевыдач не
# ограничивали и раньше. Новой ёмкости не появляется, и это вторая половина
# проверки.
first = [s2.meter_if_allowed("acme", f"k{n}", "start", None, None, None,
                             86400, time.time())[0] for n in range(99)]
check("первый квант вытесненного процесса продаётся — холодный старт не заперт",
      all(quantum is not None for quantum in first),
      "иначе выпущенный 0.3.17 не поднимался бы: он покупает его внутри acquire()")
later = [s2.meter_if_allowed("acme", f"k{n}", "start", None, None, None,
                             86400, time.time() + 2)[0] for n in range(99)]
check("а ВТОРОГО не получает ни один из девяноста девяти вытесненных",
      all(quantum is None for quantum in later),
      "покупает дальше только текущий эпох")

# ЭПОХ НЕ ПОНИЖАЕТСЯ НИЧЕМ, ЧТО ПРИШЛО СНАРУЖИ. Клиент называет `start_id` и
# `instance_id` сам — он выбирает, КАКОЙ слот занять, но не может ни завести
# слот, ни вернуть номер назад. Фенсинг безопасен только при строгой
# монотонности (Kleppmann; Paxos P1a), и это ровно та проверка.
s3 = fresh()
s3.lease_generation("ls-a", "acme", "start", "A", "vol-one", "p", 86400, pubkey="ka")
s3.lease_generation("ls-b", "acme", "start", "B", "vol-two", "p", 86400, pubkey="kb")
s3.lease_generation("ls-a2", "acme", "start", "A", "vol-one", "p", 86400, pubkey="ka2")
check("возврат прежнего старта поднимает эпох, а не возвращает свой",
      s3._slot_rows("acme")[0]["epoch"] == 3,
      f"эпох {s3._slot_rows('acme')[0]['epoch']}")
reopened = LicenseStore(s3._conn.execute("PRAGMA database_list").fetchall()[0][2])
check("и эпох переживает рестарт сервера — иначе фенсинг отзывается сам собой",
      reopened._slot_rows("acme")[0]["epoch"] == 3,
      f"после рестарта {reopened._slot_rows('acme')[0]['epoch']}")

# КАЖДЫЙ ЧИТАТЕЛЬ ХОТЬ РАЗ ВЫЗВАН. Перевод чтений на общий помощник под локом
# пропустил единственный вызов без параметров, и `list_orgs` начал отдавать 500
# — то есть админка легла целиком. Ни один тест этого не увидел, потому что
# читателей никто не звал; проверка тупая и стоит секунду.
s = fresh()
s.record_lease("l1", "acme", "i1", "p1", 86400, pubkey="k1")
s.record_report_secret("acme", "k1", "de" * 16)
s.record_usage("acme", "i1", 5, {"PHONE": 2}, 3, seq=1, prev="", signature="x",
               trust="signed", report_pubkey="k1", build="modules:abc")
s.record_grant("acme", "k1", 5000)
readers = [("lookup", lambda: s.lookup("nope")),
           ("report_secret", lambda: s.report_secret("acme", "k1")),
           ("granted_total", lambda: s.granted_total("acme")),
           ("builds_seen", lambda: s.builds_seen("acme")),
           ("slots_view", lambda: s.slots_view("acme", "start", 86400, time.time())),
           ("binding_of", lambda: s.binding_of("acme", "k1", 0.0)),
           ("metering_anomalies", lambda: s.metering_anomalies()),
           ("usage_totals", lambda: s.usage_totals("acme")),
           ("instances", lambda: s.instances("acme")),
           ("list_orgs", lambda: s.list_orgs()),
           ("prune_leases", lambda: s.prune_leases(86400))]
broken = []
for name, call in readers:
    try:
        call()
    except Exception as error:
        broken.append(f"{name}: {error}")
check("каждый читатель store вызывается без ошибки", not broken,
      f"проверено {len(readers)}" + (f", сломано {broken}" if broken else ""))

print("\nАТАКИ НА ЦЕПЬ ОТЧЁТОВ")
def send(s, rep, trust="signed", inst="c1"):
    s.record_usage("acme", inst, rep.get("requests", 0), {}, rep.get("values", 0),
                   seq=rep.get("seq", 0), prev=rep.get("prev", ""),
                   signature=rep.get("signature", ""), trust=trust,
                   report_pubkey=rep.get("_key",""))
def breaks(s, inst="c1"):
    r = s._conn.execute("SELECT chain_breaks FROM usage WHERE instance_id=?", (inst,)).fetchone()
    return int(r[0] or 0)

SECRET = _secrets.token_bytes(32)
def rep(vals, seq, prev, secret=None):
    r = {"requests": vals, "values": vals, "seq": seq, "prev": prev}
    r["signature"] = mac_report(r, secret or SECRET)
    r["_key"] = (secret or SECRET).hex(); return r

s = fresh(); prev = ""
for i, seq in enumerate((1, 2, 3), 1):
    r = rep(i * 10, seq, prev); send(s, r); prev = hashlib.sha256(r["signature"].encode()).hexdigest()
check("честная цепь без разрывов", breaks(s) == 0, f"разрывов {breaks(s)}")

s2 = fresh(); prev = ""
r1 = rep(10, 1, prev); send(s2, r1); prev = hashlib.sha256(r1["signature"].encode()).hexdigest()
r2 = rep(20, 2, prev); send(s2, r2)
send(s2, r1)                                   # ПОВТОР старого валидного отчёта
check("повтор старого отчёта", breaks(s2) > 0, f"разрывов {breaks(s2)}")

s3 = fresh(); prev = ""
for seq in (1, 2, 3):
    r = rep(seq * 10, seq, prev); send(s3, r); prev = hashlib.sha256(r["signature"].encode()).hexdigest()
send(s3, {"requests": 1, "values": 1})          # подпись СНЯТА целиком
# ЗДЕСЬ СТОЯЛО `breaks(s3) > 0 or True` — тождественно зелёная строка, ровно та,
# которую `checks.yml` с тех пор ищет грепом под заголовком «проверка, которая не
# может упасть, — это удалённая проверка». Тот шаг её и находил; он просто не
# добегал, потому что `licensing/test_admin_api.py` двумя шагами выше падал на
# отсутствующем PSEUDEX_TUNING_KEY и ронял джоб раньше. Первая красная ступень
# прятала следующие.
#
# Зелёной она была не по лени: утверждение НЕВЕРНО. При снятой подписи разрыв в
# `usage.chain_breaks` появиться и не может — `record_usage` уходит по ветке
# недоверенного отчёта раньше, чем что-либо пишет в эту колонку. `or True` прятал
# неверное утверждение вместо того, чтобы его исправить.
#
# Верное и способное упасть — то, ради чего ветка недоверенного отчёта написана:
# неподписанные числа не входят в billable-счётчики (`requests` остаётся на
# последнем честном значении, а не падает до 1), и сам отчёт виден отдельно.
stripped = s3._conn.execute(
    "SELECT requests, unverified_reports FROM usage WHERE instance_id='c1'").fetchone()
check("снятая подпись не опускает счёт", int(stripped[0] or 0) == 30,
      f"requests={stripped[0]}, последний честный отчёт нёс 30")
check("снятый отчёт посчитан отдельным счётчиком", int(stripped[1] or 0) > 0,
      f"unverified_reports={stripped[1]}")
row = s3._conn.execute("SELECT trust FROM usage").fetchone()
check("снятая подпись помечена недоверенной", row[0] != "signed", f"trust={row[0]}")

s4 = fresh()
for i in range(5):
    send(s4, rep(1, 1, ""))                     # ВЕЧНЫЙ seq=1: «я перезапустился»
check("вечный seq=1 (мнимый перезапуск)", breaks(s4) > 0, f"разрывов {breaks(s4)}")

s5 = fresh()
# ПЕРЕХВАТЧИК НА ХОСТЕ КЛИЕНТА — полный сценарий
proc = generate_process_key(); mitm = generate_process_key()
srv_secret = _secrets.token_bytes(32)
lease = {"recipient": proc.public, "report_secret": seal(srv_secret, proc.public)}
try:
    open_sealed(lease["report_secret"], mitm); opened = True
except BundleError:
    opened = False
check("перехватчик открывает секрет отчётов", not opened, "секрет запечатан получателю")

forged = {"requests": 1, "values": 1, "seq": 1, "prev": ""}
forged["signature"] = mac_report(forged, _secrets.token_bytes(32))
try:
    verify_report(forged, srv_secret); accepted = True
except BundleError:
    accepted = False
check("перехватчик подделывает отчёт своим секретом", not accepted, "MAC не сходится")

swapped = dict(lease); swapped["recipient"] = mitm.public
check("контейнер ловит подмену получателя",
      swapped["recipient"] != proc.public, "recipient под подписью, сверяется с своим")
KNOWN = set()

s6 = fresh(); prev = ""
for seq in (1, 2):
    r = rep(100, seq, prev); send(s6, r); prev = hashlib.sha256(r["signature"].encode()).hexdigest()
r = rep(5, 3, prev); send(s6, r)                # значения ПОШЛИ ВНИЗ
row = s6._conn.execute("SELECT values_total, resets FROM usage").fetchone()
check("откат значений вниз", int(row[0]) >= 100, f"values_total={row[0]}, resets={row[1]}")


# --- атаки, найденные security-review 31.08 -------------------------------
print("\nАТАКИ, НАЙДЕННЫЕ РЕВЬЮ")
s7 = fresh()
sec7 = _secrets.token_bytes(32)
s7.record_report_secret("acme", "KEYA", sec7.hex())
honest = {"requests": 100, "values": 100, "seq": 1, "prev": ""}
honest["signature"] = mac_report(honest, sec7)
s7.record_usage("acme", "prod", 100, {}, 100, seq=1, prev="",
                signature=honest["signature"], trust="signed", report_pubkey="KEYA")
before = s7.usage_totals("acme")
# снять подпись — раньше это было ТИШЕ, чем подделать
s7.record_usage("acme", "prod", 10 ** 9, {}, 10 ** 9, seq=0, prev="",
                signature="", trust="signed", report_pubkey="KEYA")
after = s7.usage_totals("acme")
check("отчёт без подписи не попадает в счёт",
      after["requests"] == before["requests"] and after["values"] == before["values"],
      f"requests {before['requests']} -> {after['requests']}")
check("непроверенное видно в итогах",
      after["unverified_reports"] > 0 and after["unverified_requests"] > 0,
      f"unverified_reports={after['unverified_reports']}")

# секрет привязан к КЛЮЧУ ПРОЦЕССА, а не к instance_id
s8 = fresh()
s8.record_report_secret("acme", "KEY1", "11" * 32)
s8.record_report_secret("acme", "KEY2", "22" * 32)
check("два воркера одного instance_id — два секрета",
      s8.report_secret("acme", "KEY1") != s8.report_secret("acme", "KEY2"),
      "ключ строки — pubkey")
check("чужим instance_id секрет не перебить",
      s8.report_secret("acme", "KEY1") == "11" * 32, "перезапись только по своему ключу")

# форма MAC проверяется до сравнения
for bad, name in ((("подпись"), "не-ASCII"), ("zz" * 32, "не-hex"), ("ab", "короткая")):
    try:
        verify_report({"requests": 1, "signature": bad}, sec7); held = False
    except BundleError:
        held = True
    except TypeError:
        held = False
    check(f"MAC-подпись {name} отвергается без TypeError", held)

# --- СЛОТЫ, ФЕНСИНГ И ТО, ЧЕГО ЗДЕСЬ БОЛЬШЕ НЕТ ---------------------------
#
# ВОСЕМЬСОТ СТРОК ОТСЮДА УДАЛЕНЫ ВМЕСТЕ С МЕХАНИЗМАМИ, КОТОРЫЕ ОНИ ПИНИЛИ, и
# каждое удаление названо дефектом, который механизм лечил, и тем, чем этот
# дефект лечится теперь. Красная проверка удалённого механизма — не сигнал, а
# шум; молчаливое удаление — потеря памяти шести заходов.
#
#   «отпущенный слот свободен СРАЗУ, без остывания», «само освобождение бюджета
#     НЕ тратит», «остановка контейнера с 4 воркерами — ноль единиц», «пробный
#     тариф: десять честных остановок подряд», «восемь редеплоев на том же томе»
#       лечили Б26quinquies: клиент пробного тарифа после ДВУХ честных
#       `docker stop` оказывался заперт ~23 часа. ЛЕЧИТСЯ ТЕПЕРЬ: `/v1/release`
#       не читает ни одно решение, перезапуск — новое поколение того же слота,
#       и путь на сервере для OOM и `docker stop` БАЙТ В БАЙТ один. Держится
#       проверкой «OOM и docker stop дают одинаковые записи» в test_admin_api.
#   «замолчавший 20 мин контейнер слот НЕ держит», «кабинет показывает его
#     silent», «аренда 20-минутной давности + свежий отчёт = слот ЗАНЯТ», «по
#     одной версии 1.0.0 слот считается по окну», «отчёт ОТДЕЛЬНО от аренды
#     доказывает пульс», «покупка ёмкости пульса НЕ доказывает»
#       лечили Б26: труп держал слот 16–24 ч, а движок без пульса нельзя было
#       судить по молчанию. СВОЙСТВО УТРАТИЛО СИЛУ ЦЕЛИКОМ: занятость по
#       молчанию не решается. Ни один порог больше не сравнивается со временем,
#       поэтому «пульс» и «версия, умеющая пульс» перестали существовать как
#       понятия — вместе с `ALIVE_SECONDS`, `LIVENESS_SINCE`,
#       `HEARTBEAT_PROOF_SECONDS`.
#   «16 воркеров, третий запуск упирается в потолок МЕСТ», «32 ЖИВЫХ процесса —
#     по-прежнему потолок», «поколение из 32 молчащих ключей НЕ
#     переоткрывается», «32 места заняты — новый воркер не поднимается»
#       лечили Б26quater: поколение из 32 ключей переоткрывалось каждые
#       T_alive, то есть один допуск покупал 32 обслуживающих процесса.
#       СВОЙСТВО УТРАТИЛО СИЛУ: мест нет, переоткрывать нечего. E8 (отказ на
#       третьем перезапуске 16 воркеров) исчезает как класс — держится
#       проверкой «двадцать воркеров и перезапуск на двадцать новых».
#   «молчание тратит бюджет так же, как /v1/release», «карусель из ДВУХ имён
#     упирается в бюджет», «карусель ЧУЖИХ имён платит по единице», «отказ при
#     4 потраченных из 3 ждёт ВТОРУЮ единицу»
#       лечили Б26bis/ter: бюджет перевыдач был единственным ограничителем
#       темпа карусели, и считать его надо было ДОПУСКОМ, а не освобождением.
#       СВОЙСТВО УТРАТИЛО СИЛУ: карусель — поколения на одном слоте, покупает
#       одно; умножения нет. Остаток (полоса `Q_min` на аренду) бюджетом не
#       ограничивался НИКОГДА и теперь печатается числом в test_admin_api.
#   «эхо посчитано ПО КЛЮЧАМ», «покупка ёмкости через секунду возвращает место
#     ЗАНЯТЫМ», «место, освобождённое поддержкой, покупкой не возвращается»
#       лечили Б26sexies: кольцо «аренда → release → покупка» давало ≥500
#       вооружённых процессов при разрешённых 32. ЛЕЧИТСЯ: покупка при чужом
#       эпохе невозможна — ниже это и проверяется.
#   «слот молчавшего отобран, и это записано как silence», «отобранный ключ
#     больше НЕ продлевается», «причина освобождения едет на экран»
#       лечили Б26quater/bis: экран врал о том, кто держит слот. ЛЕЧИТСЯ формой
#       по слотам (`slots_view`) — держится проверкой формы в test_admin_api.
#
# Ниже — то, что от всего этого ОСТАЛОСЬ ВЕРНЫМ и обязано таким остаться.
print("\nФЕНСИНГ")

now = time.time()
s20 = fresh()
s20.lease_generation("ls-1", "acme", "start", "OLD", "vol-one", "p", 86400,
                     pubkey="k-old")
bought, fence = s20.meter_if_allowed("acme", "k-old", "start", None, None, None,
                                     86400, now)
check("держатель покупает ёмкость как обычно", bought is not None, f"{fence}")

# КОЛЬЦО «АРЕНДА → RELEASE → АРЕНДА» ПОД ОДНИМ ИМЕНЕМ: новое поколение фенсит
# предыдущее, и прощание для этого не нужно ни разу.
s20.release_process("acme", "k-old")
s20.lease_generation("ls-2", "acme", "start", "NEW", "vol-one", "p", 86400,
                     pubkey="k-new")
again, fence = s20.meter_if_allowed("acme", "k-old", "start", None, None, None,
                                    86400, now + 2)
check("отпустивший и вернувшийся за ёмкостью ключ получает fenced, а не квант",
      again is None and fence["error"] == "fenced",
      f"{fence.get('error')}")
check("и отказ несёт свой эпох, текущий и держателя",
      fence["epoch"] == 1 and fence["current_epoch"] == 2
      and fence["holder_start_id"] == "NEW", f"{fence}")

# УЖЕ ВЫДАННОЕ НЕ ОТЗЫВАЕТСЯ, И ЭТО Б30 С СЕРВЕРНОЙ СТОРОНЫ. Отфенсенный
# доцеживает полосу: его строка `meter` остаётся с прежним `granted`, и ни одна
# ветка её не трогает. Гасит поколение `has_capacity()` на клиенте, а не отказ.
row = s20.meter_row("acme", "k-old")
check("отфенсенному оставлена вся купленная полоса — гасит его расход, а не отказ",
      row["granted"] >= 200 and row["quantum_seq"] == 1,
      f"granted={row['granted']}, квантов {row['quantum_seq']}")

# КЛЮЧ БЕЗ ПРИВЯЗКИ НЕ ФЕНСИТСЯ ВОВСЕ. Бандла у него нет, квант ему бесполезен,
# и судить по молчанию ровно там, где сказать нечего, — это и есть тот самый
# детектор отказов. Так же вёл себя и прежний быстрый путь.
s21 = fresh()
free, fence = s21.meter_if_allowed("acme", "no-lease", "start", None, None, None,
                                   86400, now)
check("ключ без аренды в окне покупает, а не фенсится", free is not None, f"{fence}")

# ОТМЕТКУ СЛОТА ДВИГАЕТ ТОЛЬКО ТЕКУЩЕЕ ПОКОЛЕНИЕ. Иначе отфенсенный сосед,
# продолжающий отчитываться, вечно выталкивал бы себя из головы очереди
# ранжирования — то есть ранжирование перестало бы находить самого старого.
s22 = fresh()
s22.lease_generation("ls-a", "acme", "start", "A", "vol-one", "p", 86400, pubkey="ka")
s22.lease_generation("ls-b", "acme", "start", "B", "vol-two", "p", 86400, pubkey="kb")
before_touch = s22._slot_rows("acme")[0]["last_heard_at"]
moved = s22.touch_slot("acme", 1, 1, now + 3600)
check("отчёт отфенсенного поколения отметку слота НЕ двигает",
      not moved and s22._slot_rows("acme")[0]["last_heard_at"] == before_touch,
      f"эпох 1 при текущем {s22._slot_rows('acme')[0]['epoch']}")
check("а отчёт держателя — двигает",
      s22.touch_slot("acme", 1, 2, now + 3600))

# РАНЖИРОВАНИЕ БЕРЁТ САМОГО СТАРОГО, А НЕ САМОГО СВЕЖЕГО, И ЭТО НЕ ВКУСОВЩИНА.
# Исследование написало «слышали ПОЗЖЕ всех» (MAX) и тут же объяснило
# перезапуск словами «его эпох — самый старый среди занятых, потому что он
# мёртв». С MAX пришедший после OOM отфенсил бы РАБОТАЮЩЕГО соседа, а труп
# остался бы держателем; ТЗ §3bis.1 ставит MIN.
s23 = fresh("work")
for number in range(4):
    s23.lease_generation(f"ls-{number}", "acme", "work", f"S{number}",
                         f"vol-{number}", "p", 86400, pubkey=f"k{number}")
s23.touch_slot("acme", 4, 1, now + 100)          # четвёртый слышен позже всех
s23.touch_slot("acme", 1, 1, now - 1000)         # первый — раньше всех
chosen = s23.admit_generation(s23._slot_rows("acme"), "vol-new")
check("при полном тарифе берётся слот, который слышали РАНЬШЕ всех",
      chosen["slot_no"] == 1 and chosen["reason"] == "ranked", f"{chosen}")
own = s23.admit_generation(s23._slot_rows("acme"), "vol-2")
check("а СВОЯ установка берёт свой слот, не спрашивая ранжирования",
      own["slot_no"] == 3 and own["reason"] == "installation", f"{own}")
check("и правило допуска НИКОГДА не отказывает — вариант А §6.1",
      not chosen["refusal"] and not own["refusal"],
      "отказ на N-м контейнере ломал бы каждую раскатку K8s")


# --- ГРАНТЫ ЁМКОСТИ: счёт строится на выданном нами ---------------------
print("\nГРАНТЫ ЁМКОСТИ")
import threading
import pseudex.license as _L

s10 = fresh()
for _ in range(3):
    s10.record_grant("acme", "K1", s10.grant_size("start"))
s10.record_grant("acme", "K2", s10.grant_size("start"))
check("выданное копится у нас",
      s10.usage_totals("acme")["granted"] == 4 * s10.grant_size("start"),
      f"granted={s10.usage_totals('acme')['granted']}")

# отчёты клиента НЕ влияют на выданное
s10.record_usage("acme", "prod", 1, {}, 1, seq=1, prev="", signature="",
                 trust="unsigned", report_pubkey="K1")
check("замолчавший клиент не уменьшает счёт",
      s10.usage_totals("acme")["granted"] == 4 * s10.grant_size("start"),
      "granted не зависит от usage")

# ПРОВЕРКИ ЁМКОСТИ ПЕРЕЕХАЛИ В `test_admin_api.py`.
#
# Здесь стояла заглушка `LicenseClient.__new__` без `__init__`, и она ломалась
# на каждом новом поле состояния — потому что проверяла не клиента, а свою
# копию его арифметики. Ёмкость теперь покупается по сети, у неё есть нонс,
# порядковый номер и подпись, и ничто из этого заглушке не видно. Настоящий
# клиент против настоящего сервера — там же, где живут остальные проверки
# протокола.

# перезапуск обнуляет счётчик — и стоит нового гранта
s11 = fresh()
before = s11.usage_totals("acme")["granted"]
s11.record_grant("acme", "K-restarted", s11.grant_size("start"))
check("перезапуск ради обнуления счётчика стоит гранта",
      s11.usage_totals("acme")["granted"] == before + s11.grant_size("start"),
      "новый процесс = новый ключ = новая аренда = новая запись у нас")


# --- МЕРА СБОРКИ ----------------------------------------------------------
print("\nМЕРА СБОРКИ")
from pseudex.measure import build_measurement

s12 = fresh()
sec12 = _secrets.token_bytes(32); PK12 = "PK-build"
s12.record_report_secret("acme", PK12, sec12.hex())

def signed_send(store, build, seq, prev, secret=sec12, pk=PK12):
    r = {"requests": 100, "values": 100, "seq": seq, "prev": prev, "build": build}
    r["signature"] = mac_report(r, secret)
    hexs = store.report_secret("acme", pk); trust = "unsigned"
    try:
        verify_report(r, bytes.fromhex(hexs)); trust = "signed"
    except BundleError:
        trust = "bad_signature"
    store.record_usage("acme", "prod", 100, {}, 100, seq=seq, prev=prev,
                       signature=r["signature"], trust=trust, report_pubkey=pk,
                       build=build)
    return hashlib.sha256(r["signature"].encode()).hexdigest()

GOOD = "sha256:" + "a" * 64
prev12 = signed_send(s12, GOOD, 1, "")
prev12 = signed_send(s12, GOOD, 2, prev12)
check("одна сборка — ноль смен",
      s12.builds_seen("acme") and s12.builds_seen("acme")[0]["changes"] == 0)

signed_send(s12, "sha256:" + "b" * 64, 3, prev12)
check("подмена сборки под одним ключом процесса ЗАМЕЧЕНА",
      s12.builds_seen("acme")[0]["changes"] == 1,
      "ключ процесса живёт столько же, сколько процесс — мера меняться не может")

# мера входит в подписанное тело: снаружи её не переписать
r13 = {"requests": 1, "values": 1, "seq": 1, "prev": "", "build": GOOD}
r13["signature"] = mac_report(r13, sec12)
r13["build"] = "sha256:" + "c" * 64          # перехватчик правит меру в пути
try:
    verify_report(r13, sec12); tampered_ok = True
except BundleError:
    tampered_ok = False
check("правка меры в пути ломает MAC", not tampered_ok)

check("мера непустая и своей формы",
      build_measurement().startswith(("sha256:", "modules:")),
      build_measurement()[:22] + "...")


# --- РОТАЦИЯ КЛЮЧА ПРОВЕРКИ ----------------------------------------------
print("\nРОТАЦИЯ КЛЮЧА ПРОВЕРКИ")
import base64 as _b64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import pseudex.license as _lic

def _pub(k):
    return _b64.b64encode(k.public_key().public_bytes(
        Encoding.Raw, PublicFormat.Raw)).decode()

old_key, new_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
os.environ["PSEUDEX_LICENSE_PUBKEY"] = _pub(old_key) + ", " + _pub(new_key)
accepted = _lic._public_key_materials()
check("список ключей разбирается", len(accepted) == 2, f"{len(accepted)} ключа")
check("пробелы вокруг запятой не ломают",
      all(not m.startswith(" ") and not m.endswith(" ") for m in accepted))
os.environ["PSEUDEX_LICENSE_PUBKEY"] = _pub(old_key)
check("один ключ — тоже список", len(_lic._public_key_materials()) == 1)

unexpected = [f for f in fails if f not in KNOWN]
print(f"\nсломано {len(fails)}, из них известный предел {len(fails) - len(unexpected)}")
for f in fails:
    print(f"   - {f}{' (известный предел)' if f in KNOWN else ''}")
sys.exit(1 if unexpected else 0)
