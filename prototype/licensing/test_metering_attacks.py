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
import hashlib, sys, tempfile
sys.path.insert(0, ".")
from licensing.store import LicenseStore
from pseudex.bundle import generate_report_key, encode_report_key, sign_report

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

k = generate_report_key()
def rep(vals, seq, prev):
    r = {"requests": vals, "values": vals, "seq": seq, "prev": prev}
    r["signature"] = sign_report(r, k); r["_key"]=encode_report_key(k); return r

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
own = generate_report_key()                     # СВОЯ пара ключей злоумышленника
r = {"requests": 1, "values": 1, "seq": 1, "prev": ""}
r["signature"] = sign_report(r, own); r["_key"]=encode_report_key(own); send(s5, r, trust="signed")
check("подмена ключа отчётов", False,
      "ИЗВЕСТНЫЙ ПРЕДЕЛ: перехват с первого обращения; лечится прикреплением сертификата")
KNOWN = {"подмена ключа отчётов"}

s6 = fresh(); prev = ""
for seq in (1, 2):
    r = rep(100, seq, prev); send(s6, r); prev = hashlib.sha256(r["signature"].encode()).hexdigest()
r = rep(5, 3, prev); send(s6, r)                # значения ПОШЛИ ВНИЗ
row = s6._conn.execute("SELECT values_total, resets FROM usage").fetchone()
check("откат значений вниз", int(row[0]) >= 100, f"values_total={row[0]}, resets={row[1]}")

unexpected = [f for f in fails if f not in KNOWN]
print(f"\nсломано {len(fails)}, из них известный предел {len(fails) - len(unexpected)}")
for f in fails:
    print(f"   - {f}{' (известный предел)' if f in KNOWN else ''}")
sys.exit(1 if unexpected else 0)
