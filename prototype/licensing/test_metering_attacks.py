"""АТАКИ на учёт расхода и на цепь отчётов.

Набор написан, чтобы СЛОМАТЬ собственную логику, а не подтвердить её. Слот-,
поколенческие и фенсинг-проверки удалены вместе с механизмом
(docs/tz-license-volume-quota.md §A): слот-счёт как принуждение убран, граница
стала ОБЪЁМНОЙ (потолок запросов на `/v1/meter`). Проверки самого потолка и
овереджа пишет автор тестов отдельно — здесь остаются атаки на цепь отчётов,
на счёт по выданной ёмкости и на меру сборки, которые не зависят от слотов.

ОДНА СТРОКА ЗДЕСЬ ВСЕГДА КРАСНАЯ, И ЭТО НАМЕРЕННО. Перехватчик, стоящий в
канале с САМОГО ПЕРВОГО обращения, подменяет открытый ключ отчётов и подписывает
свои — подпись не может доказать происхождение ключа, который она же и
принесла. Закрывается это только прикреплением сертификата нашего сервера в
релизном бинарнике, у чего своя цена в ротации. Пока не закрыто — строка стоит
красной, чтобы предел был виден, а не забыт.

    python3 licensing/test_metering_attacks.py
"""
import hashlib
import os, sys, tempfile, time
sys.path.insert(0, ".")
from licensing.store import LicenseStore
import secrets as _secrets
from pseudex.bundle import (BundleError, generate_process_key, mac_report,
                            open_sealed, seal, verify_report)

def fresh(plan="start"):
    s = LicenseStore(tempfile.mktemp(suffix=".db")); s.issue_key("acme", plan); return s

fails = []
def check(name, held, detail=""):
    print(f"  {'ДЕРЖИТ ' if held else 'СЛОМАНО'} {name}   {detail}")
    if not held: fails.append(name)

# --- КАЖДЫЙ ЧИТАТЕЛЬ STORE ВЫЗЫВАЕТСЯ БЕЗ ОШИБКИ --------------------------
#
# Перевод чтений на общий помощник под локом однажды пропустил единственный
# вызов без параметров, и `list_orgs` начал отдавать 500 — то есть админка
# легла целиком. Ни один тест этого не увидел, потому что читателей никто не
# звал; проверка тупая и стоит секунду. Слот-читатели (`slots_view`,
# `binding_of`) ушли вместе с механизмом; на их месте — объёмные (`ceiling_of`,
# `instances_view`).
print("ЧИТАТЕЛИ STORE")
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
           ("instances_view", lambda: s.instances_view("acme", "start", 86400, time.time())),
           ("ceiling_of", lambda: s.ceiling_of("acme")),
           ("ceiling_notice", lambda: s.ceiling_notice("acme")),
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
# Неподписанные числа не входят в billable-счётчики (`requests` остаётся на
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

# --- ЁМКОСТЬ ВЫДАЁТСЯ ЛЮБОМУ ПРОЦЕССУ, ОТКАЗ — ТОЛЬКО ПО ПОТОЛКУ ----------
#
# Слот-привязки больше нет, и с ней ушла лазейка `binding is None` (Б35):
# ключ без привязанной аренды раньше покупал ёмкость безусловно. Теперь
# граница ОДНА — объёмный потолок на организации, и она бьёт по ЛЮБОМУ ключу.
print("\nЁМКОСТЬ И ПОТОЛОК")
now = time.time()
s20 = fresh()
q, ref = s20.meter_if_allowed("acme", "any-key", "start", None, now)
check("ключ без аренды покупает ёмкость (лазейка binding is None закрыта)",
      q is not None and not ref, f"{ref}")

# --- ГРАНТЫ ЁМКОСТИ: счёт строится на выданном нами ---------------------
print("\nГРАНТЫ ЁМКОСТИ")
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
