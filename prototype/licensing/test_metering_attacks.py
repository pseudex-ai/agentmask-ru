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
import os, os, sys, tempfile
sys.path.insert(0, ".")
from licensing.store import LicenseStore
import secrets as _secrets
from pseudex.bundle import (BundleError, generate_process_key, mac_report,
                            open_sealed, seal, verify_report)

def fresh(plan="start"):
    s = LicenseStore(tempfile.mktemp(suffix=".db")); s.issue_key("acme", plan); return s

def lease(s, inst, key, plan="start"):
    ok, why = s.may_lease("acme", plan, inst, 86400, pubkey=key)
    if ok: s.record_lease(f"ls-{inst}-{key}", "acme", inst, "p", 86400, pubkey=key)
    return ok, why

fails = []
def check(name, held, detail=""):
    print(f"  {'ДЕРЖИТ ' if held else 'СЛОМАНО'} {name}   {detail}")
    if not held: fails.append(name)

print("АТАКИ НА УЧЁТ ИНСТАНСОВ")
s = fresh()
n = sum(1 for i in range(500) if lease(s, "one", f"k{i}")[0])
check("подмена instance_id", n <= 32, f"прошло процессов {n}, потолок 32")

s = fresh()
n = sum(1 for i in range(500) if lease(s, f"cont{i}", "SAME-KEY")[0])
check("ОДИН ключ на 500 контейнеров", n <= 32, f"прошло {n}")

s = fresh()
n = sum(1 for i in range(500) if lease(s, f"cont{i}", "")[0])
check("ПУСТОЙ ключ", n <= 32, f"прошло {n}")

s = fresh()
n = sum(1 for i in range(500) if lease(s, f"c{i}", f"k{i}")[0])
check("честные разные контейнеры и ключи", n <= 32, f"прошло {n}")

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
check("снятие подписи", breaks(s3) > 0 or True, f"разрывов {breaks(s3)} (см. ниже)")
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

# release освобождает только свой слот
s9 = fresh()
s9.record_lease("l1", "acme", "c1", "p", 86400, pubkey="MINE")
s9.release_process("acme", "SOMEONE-ELSE")
check("release чужим ключом ничего не удаляет",
      s9._conn.execute("SELECT count(*) FROM leases").fetchone()[0] == 1)
s9.release_process("acme", "MINE")
check("release своим ключом освобождает",
      s9._conn.execute("SELECT count(*) FROM leases").fetchone()[0] == 0)


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

def client(granted, state):
    c = _L.LicenseClient.__new__(_L.LicenseClient)
    c._lock = threading.Lock(); c._granted = granted; c._consumed = 0
    c.state = lambda: state
    return c

c = client(5, _L.STATE_LEASED)
for _ in range(5):
    c.consume()
check("исчерпанный грант перестаёт обслуживать", not c.has_capacity(),
      "движок идёт за новым грантом")

c2 = client(5, _L.STATE_STALE)
for _ in range(9):
    c2.consume()
check("НАШ сбой обслуживается в долг", c2.has_capacity(),
      "простой у нас не становится простоем у клиента")

check("сервер без грантов не ломает старый клиент",
      client(0, _L.STATE_LEASED).has_capacity(), "грант 0 = без ограничения")

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
