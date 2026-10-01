#!/usr/bin/env python3
"""Build the BOUNDED synthetic perf corpus for the O-DETECT isolated run.

Why this file exists at all: RUNBOOK-PERF §0.3 requires a frozen corpus in the
run's OWN folder with 300-1000 messages and a deterministic order, and forbids
reading the 359-ID holdout or the paid run directory. The existing generators
(`prototype/make_*.py`) write gitignored datasets into `prototype/` (outside this
run's write scope) and two of them consume held-out/real-speech sources. So this
generator is written from scratch here, in scope.

PROVENANCE, STATED PLAINLY:
  * Every message is generated from the templates and vocabulary IN THIS FILE,
    with `random.Random(SEED)`. No real-speech utterance, no transcript, no
    corpus file and no `prototype/*.json` dataset is read or copied.
  * The values are fabricated. Checksums are computed with the STANDARD public
    algorithms (СНИЛС mod-101, ИНН weight vectors, Luhn, ОГРН mod-11) so that the
    product's checksum-gated recognizers actually fire; `--verify` re-checks every
    generated value against the ENGINE's own validators (import-time only, read
    only, nothing in `prototype/` is written) and records the counts.
  * The corpus is a COST input, not a quality input. It carries no gold labels and
    no precision/recall claim is made from it anywhere in this run.

Usage (from `prototype/`, as RUNBOOK-PERF §2 does):
    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
      ../research/quality-sprint-2026-09-30/work/D0/perf-isolated/gen_corpus.py \
      --out ../research/quality-sprint-2026-09-30/work/D0/perf-isolated
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

# `python <path>/gen_corpus.py` puts the SCRIPT's directory on sys.path[0], not the
# cwd — so `import pseudex` fails even though the runbook runs us from
# `prototype/`. Add `prototype/` explicitly instead of relying on the caller's cwd.
PROTO = Path(__file__).resolve().parents[5] / "prototype"
if str(PROTO) not in sys.path:
    sys.path.insert(0, str(PROTO))

SEED = 20260930
DEFAULT_N = 500

# Registers, and how many messages each contributes. The mixture is the point:
# 1:1 detect cost is dominated by message SHAPE, so a corpus of one shape would
# produce a p95 that describes the generator rather than the detector.
REGISTER_PLAN = (
    ("kv", 125),        # typed key-value: JSON, form fields, `name=value` lists
    ("prose", 150),     # free prose: business letters, statements (40 negatives)
    ("chat", 125),      # chat register: short, lowercase, no punctuation
    ("sloppy", 100),    # chat register with typos, missed separators, glued tokens
)
NEGATIVE_PROSE = 40     # subset of `prose` that carries NO person-like PII

MALE_FIRST = ["Иван", "Пётр", "Сергей", "Алексей", "Дмитрий", "Николай", "Андрей",
              "Михаил", "Владимир", "Егор", "Артём", "Кирилл", "Максим", "Роман",
              "Тимур", "Ашот", "Глеб", "Вадим"]
FEMALE_FIRST = ["Анна", "Мария", "Ольга", "Елена", "Татьяна", "Ирина", "Светлана",
                "Наталья", "Ксения", "Дарья", "Полина", "Юлия", "Вера", "Алина"]
MALE_PATR = ["Иванович", "Петрович", "Сергеевич", "Алексеевич", "Дмитриевич",
             "Николаевич", "Андреевич", "Михайлович", "Олегович", "Викторович"]
FEMALE_PATR = ["Ивановна", "Петровна", "Сергеевна", "Алексеевна", "Дмитриевна",
               "Николаевна", "Андреевна", "Михайловна", "Олеговна", "Викторовна"]
SURNAMES = ["Иванов", "Петров", "Смирнов", "Кузнецов", "Соколов", "Попов",
            "Лебедев", "Козлов", "Новиков", "Морозов", "Волков", "Егоров",
            "Павлов", "Семёнов", "Голубев", "Виноградов", "Богданов",
            "Воробьёв", "Фёдоров", "Михайлов", "Беляев", "Тарасов", "Белов",
            "Комаров", "Орлов", "Киселёв", "Макаров", "Мкртчян", "Шевченко"]
TRANSLIT = {"Иванов": "ivanov", "Петров": "petrov", "Смирнов": "smirnov",
            "Кузнецов": "kuznetsov", "Соколов": "sokolov", "Попов": "popov",
            "Лебедев": "lebedev", "Козлов": "kozlov", "Новиков": "novikov",
            "Морозов": "morozov", "Волков": "volkov", "Егоров": "egorov",
            "Павлов": "pavlov", "Семёнов": "semenov", "Голубев": "golubev",
            "Виноградов": "vinogradov", "Богданов": "bogdanov",
            "Воробьёв": "vorobev", "Фёдоров": "fedorov", "Михайлов": "mihailov",
            "Беляев": "belyaev", "Тарасов": "tarasov", "Белов": "belov",
            "Комаров": "komarov", "Орлов": "orlov", "Киселёв": "kiselev",
            "Макаров": "makarov", "Мкртчян": "mkrtchyan", "Шевченко": "shevchenko"}
CITIES = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск", "Екатеринбург",
          "Нижний Новгород", "Самара", "Ростов-на-Дону", "Уфа", "Пермь",
          "Воронеж", "Краснодар", "Сочи", "Тверь", "Тула", "Ярославль"]
STREETS = ["Тверская", "Ленина", "Гагарина", "Пушкина", "Советская", "Мира",
           "Садовая", "Центральная", "Школьная", "Лесная", "Победы", "Кирова",
           "Гоголя", "Чехова", "Лермонтова", "Некрасова", "Свободы", "Дружбы",
           "Юбилейная", "Солнечная", "Мкртчян"]
STREET_TYPES = ["улица", "ул.", "проспект", "пр-т", "переулок", "пер.",
                "бульвар", "шоссе", "проезд", "набережная", "площадь"]
COMPANIES = ["ООО «Заря»", "ООО «Ромашка»", "АО «Северсталь-М»", "ИП Смирнов",
             "ООО «ТехноПарк»", "ООО «Логистик Плюс»", "ООО «Вектор»",
             "АО «Каскад»", "ООО «Прима»", "ООО «Альфа-Сервис»"]
DOMAINS = ["mail.ru", "yandex.ru", "gmail.com", "corp.ru", "example.com",
           "bk.ru", "list.ru"]
POSITIONS = ["генерального директора", "главного бухгалтера", "менеджера",
             "инженера", "юриста", "руководителя отдела", "аналитика"]


# ------------------------------------------------------------- check digits --

def snils_valid(digits: str) -> bool:
    if len(digits) != 11:
        return False
    total = sum(int(digits[i]) * (9 - i) for i in range(9))
    check = 0 if total in (100, 101) else (total if total < 100 else total % 101)
    if check == 100:
        check = 0
    return check == int(digits[9:])


def inn10_valid(digits: str) -> bool:
    if len(digits) != 10:
        return False
    w = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    return sum(int(digits[i]) * w[i] for i in range(9)) % 11 % 10 == int(digits[9])


def inn12_valid(digits: str) -> bool:
    if len(digits) != 12:
        return False
    w11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    w12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    c11 = sum(int(digits[i]) * w11[i] for i in range(10)) % 11 % 10
    c12 = sum(int(digits[i]) * w12[i] for i in range(11)) % 11 % 10
    return c11 == int(digits[10]) and c12 == int(digits[11])


def luhn_valid(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        num = int(char)
        if index % 2 == 1:
            num *= 2
            if num > 9:
                num -= 9
        total += num
    return total % 10 == 0


def ogrn13_valid(digits: str) -> bool:
    return len(digits) == 13 and int(digits[:12]) % 11 % 10 == int(digits[12])


def _complete(base: str, check) -> str:
    return base + str(check(base))


def mk_snils(rng: random.Random) -> str:
    while True:
        base = "".join(str(rng.randint(0, 9)) for _ in range(9))
        if base[0] == "0":                  # keep the value inside a real-looking range
            continue
        for extra in range(100):            # mod-101 always admits exactly one check pair
            cand = base + f"{extra:02d}"
            if snils_valid(cand):
                return f"{cand[:3]}-{cand[3:6]}-{cand[6:9]} {cand[9:]}"


def mk_inn10(rng: random.Random, region: str = "77") -> str:
    base = region + "".join(str(rng.randint(0, 9)) for _ in range(7))
    return _complete(base, lambda s: sum(int(s[i]) * [2, 4, 10, 3, 5, 9, 4, 6, 8][i]
                                        for i in range(9)) % 11 % 10)


def mk_inn12(rng: random.Random) -> str:
    base = "77" + "".join(str(rng.randint(0, 9)) for _ in range(8))
    c11 = sum(int(base[i]) * [7, 2, 4, 10, 3, 5, 9, 4, 6, 8][i]
              for i in range(10)) % 11 % 10
    base11 = base + str(c11)
    c12 = sum(int(base11[i]) * [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8][i]
              for i in range(11)) % 11 % 10
    return base11 + str(c12)


def mk_card(rng: random.Random, mii: str = "4") -> str:
    """Append the Luhn digit by SEARCHING for it with the same validator.

    The first version computed the checksum over the 15-digit body and appended
    it — which flips the doubling parity: adding 1 digit moves every body digit
    one position, so the body's last digit becomes `reversed index 1` and must be
    doubled, while the body-only pass had left it undoubled. The engine's own
    validator caught it: 20/200 generated cards passed (exactly the 1-in-10 that
    a wrong parity yields by luck). Searching 10 candidates cannot be wrong.
    """
    body = mii + "".join(str(rng.randint(0, 9)) for _ in range(14))
    for check in range(10):
        if luhn_valid(body + str(check)):
            return body + str(check)
    raise AssertionError("Luhn admits no check digit for a 15-digit body")


def mk_ogrn(rng: random.Random) -> str:
    base = "1" + "".join(str(rng.randint(0, 9)) for _ in range(11))
    return _complete(base, lambda s: int(s) % 11 % 10)


# ------------------------------------------------------------------ values ---

class Person:
    __slots__ = ("first", "patr", "sur_m", "sur_f", "female", "full", "short", "email_local")

    def __init__(self, rng: random.Random) -> None:
        self.female = rng.random() < 0.5
        self.first = rng.choice(FEMALE_FIRST if self.female else MALE_FIRST)
        self.patr = rng.choice(FEMALE_PATR if self.female else MALE_PATR)
        self.sur_m = rng.choice(SURNAMES)
        self.sur_f = self.sur_m + "а" if not self.sur_m.endswith(("ко", "ян")) else self.sur_m
        sur = self.sur_f if self.female else self.sur_m
        self.full = f"{sur} {self.first} {self.patr}"
        self.short = f"{self.first} {sur}"
        self.email_local = f"{TRANSLIT.get(self.sur_m, 'user')}.{self.first[0].lower()}"


def address(rng: random.Random, full: bool = True) -> str:
    city = rng.choice(CITIES)
    st, tp = rng.choice(STREETS), rng.choice(STREET_TYPES)
    house = rng.randint(1, 120)
    flat = rng.randint(1, 250)
    if not full:
        return f"{tp} {st} {house}"
    tail = f", кв. {flat}" if rng.random() < 0.5 else ""
    return f"г. {city}, {tp} {st}, д. {house}{tail}"


def phone(rng: random.Random) -> str:
    d = "9" + "".join(str(rng.randint(0, 9)) for _ in range(9))
    style = rng.random()
    if style < 0.34:
        return f"+7 {d[:3]} {d[3:6]}-{d[6:8]}-{d[8:]}"
    if style < 0.67:
        return f"8{d}"
    return f"+7({d[:3]}){d[3:6]}-{d[6:8]}-{d[8:]}"


def email(rng: random.Random, person: Person) -> str:
    return f"{person.email_local}@{rng.choice(DOMAINS)}"


def passport(rng: random.Random) -> str:
    return f"{rng.randint(40, 49)} {rng.randint(10, 25)} {rng.randint(100000, 999999)}"


def dob(rng: random.Random) -> str:
    day, month = rng.randint(1, 28), rng.randint(1, 12)
    year = rng.randint(1955, 2004)
    if rng.random() < 0.5:
        return f"{day:02d}.{month:02d}.{year}"
    return f"{day} {['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'][month-1]} {year} г."


def date_like(rng: random.Random) -> str:
    return f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(2023, 2026)}"


def cname(rng: random.Random) -> str:
    return rng.choice(COMPANIES)


# --------------------------------------------------------------- generators --

def gen_kv(rng: random.Random) -> str:
    p, ph, em, ad = Person(rng), phone(rng), None, address(rng)
    em = email(rng, p)
    kind = rng.randrange(6)
    if kind == 0:
        return json.dumps({"customer_name": p.full, "phone": ph, "email": em,
                           "address": ad}, ensure_ascii=False)
    if kind == 1:
        return (f"Заявка #{rng.randint(1000, 9999)}: ФИО — {p.full}; "
                f"телефон {ph}; ИНН {mk_inn10(rng)}; адрес {ad}.")
    if kind == 2:
        return (f'<form><field name="client">{p.full}</field>'
                f'<field name="phone">{ph}</field>'
                f'<field name="passport">паспорт {passport(rng)}</field></form>')
    if kind == 3:
        return json.dumps({"contractor": {"name": cname(rng), "inn": mk_inn10(rng),
                                          "ogrn": mk_ogrn(rng)},
                           "contact": {"person": p.full, "phone": ph}},
                          ensure_ascii=False)
    if kind == 4:
        return f"snils={mk_snils(rng)}; card={mk_card(rng)}; dob={dob(rng)}"
    return (f"Анкета: имя={p.full}, дата рождения={dob(rng)}, "
            f"СНИЛС={mk_snils(rng)}, e-mail={em}, тел={ph}")


def gen_prose(rng: random.Random, negative: bool) -> str:
    if negative:
        kind = rng.randrange(3)
        if kind == 0:
            return (f"Счёт № {rng.randint(100, 9999)} от {date_like(rng)} на сумму "
                    f"{rng.randint(1000, 900000)} руб. оплачен. Заказ № "
                    f"{rng.randint(10000, 99999)}, трек-номер RU{rng.randint(10**9, 10**10-1)}, "
                    f"артикул {rng.randint(1000, 9999)}. Просим подтвердить акт сверки "
                    f"за {rng.choice(['I', 'II', 'III', 'IV'])} квартал.")
        if kind == 1:
            return (f"Совещание перенесено на {date_like(rng)} в "
                    f"{rng.randint(9, 18)}:{rng.choice(['00', '30'])} в переговорной на "
                    f"{rng.randint(2, 9)} этаже. Повестка: бюджет {rng.randint(1, 40)} млн, "
                    f"сроки, отчёт по проекту № {rng.randint(100, 999)}.")
        return (f"По договору № {rng.randint(100, 9999)}-{rng.randint(2023, 2026)} "
                f"поставка выполнена в срок. Претензий по качеству нет. "
                f"Оригиналы документов направлены {date_like(rng)} курьерской службой.")
    p, ph, em, ad = Person(rng), phone(rng), None, address(rng)
    em = email(rng, p)
    kind = rng.randrange(4)
    if kind == 0:
        return (f"Прошу согласовать договор с {cname(rng)} в лице {p.full}, "
                f"{rng.choice(POSITIONS)}. Контактный телефон {ph}, почта {em}. "
                f"Юридический адрес: {ad}. ИНН {mk_inn10(rng)}.")
    if kind == 1:
        return (f"Добрый день! Направляю данные сотрудника: {p.full}, дата рождения "
                f"{dob(rng)}, паспорт {passport(rng)}, зарегистрирован по адресу {ad}. "
                f"Прошу оформить пропуск.")
    if kind == 2:
        return (f"По заявке клиента {p.full} (ИНН {mk_inn12(rng)}) просим доставить "
                f"заказ по адресу {ad}. Связаться можно по номеру {ph} "
                f"или по почте {em}.")
    return (f"Пациент {p.full}, {rng.randint(20, 88)} лет, обратился с жалобами. "
            f"Направление № {rng.randint(100, 9999)} от {date_like(rng)}. "
            f"Телефон для связи {ph}. Зарегистрирован: {ad}.")


def gen_chat(rng: random.Random) -> str:
    p, ph = Person(rng), phone(rng)
    kind = rng.randrange(6)
    if kind == 0:
        return (f"привет, скинь реквизиты на {email(rng, p)}, я сейчас на "
                f"{rng.choice(STREETS)} {rng.randint(1, 60)}, позвони {ph}")
    if kind == 1:
        return f"ок, {p.first} подтвердил, кидай на карту {mk_card(rng)}"
    if kind == 2:
        return f"он сказал что снилс {mk_snils(rng)}, пробей плиз"
    if kind == 3:
        return (f"{p.first}, ты где? я у метро, адрес "
                f"{rng.choice(CITIES)}, {rng.choice(STREETS)} {rng.randint(1, 90)}")
    if kind == 4:
        return f"закинь инн {mk_inn10(rng)} в договор и всё"
    return (f"спасибо! {p.first}, {ph} это его номер? напиши на "
            f"{email(rng, p)}")


def gen_sloppy(rng: random.Random) -> str:
    p = Person(rng)
    kind = rng.randrange(6)
    if kind == 0:
        return (f"{p.full.lower()} паспорт {passport(rng)} прописан "
                f"{rng.choice(CITIES).lower()} {rng.choice(STREETS).lower()} "
                f"{rng.randint(1, 90)} кв {rng.randint(1, 200)} тел {phone(rng)}")
    if kind == 1:
        return f"снилс {mk_snils(rng)} инн {mk_inn12(rng)} карта {mk_card(rng)} все данные скинул"
    if kind == 2:
        return (f"тут {p.short.lower()} просил позвонить на {phone(rng)} и написать на "
                f"{email(rng, p)}")
    if kind == 3:
        return (f"адрес доставки {rng.choice(CITIES).lower()} "
                f"{rng.choice(STREETS).lower()} {rng.randint(1, 80)} дом "
                f"{rng.randint(1, 40)} корп {rng.randint(1, 5)} кв {rng.randint(1, 300)}")
    if kind == 4:
        return (f"его жена {Person(rng).short.lower()} работает в {cname(rng).lower()} "
                f"тел {phone(rng)}")
    return (f"зака3 {rng.randint(100, 999)} на {p.short.lower()} доставка "
            f"{rng.choice(CITIES)} ул {rng.choice(STREETS)} {rng.randint(1, 70)}")


# ------------------------------------------------------------------- build ---

def build(n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    plan: list[str] = []
    for register, count in REGISTER_PLAN:
        plan.extend([register] * count)
    while len(plan) < n:
        plan.append("prose")
    plan = plan[:n]
    rng.shuffle(plan)                       # deterministic order, mixed registers

    neg_slots = set(rng.sample([i for i, r in enumerate(plan) if r == "prose"],
                               NEGATIVE_PROSE))
    out: list[dict] = []
    for index, register in enumerate(plan):
        if register == "kv":
            text = gen_kv(rng)
        elif register == "prose":
            text = gen_prose(rng, negative=index in neg_slots)
        elif register == "chat":
            text = gen_chat(rng)
        else:
            text = gen_sloppy(rng)
        assert "\n" not in text and "\t" not in text
        out.append({"id": index, "register": register, "text": text})
    return out


def verify() -> dict:
    """Re-check every generated identifier against the ENGINE's validators.

    Read-only: imports `pseudex.ru_pii` and calls four pure functions. Nothing
    under `prototype/` is written (PYTHONDONTWRITEBYTECODE=1 is required by the
    runbook and is asserted by the caller).
    """
    from pseudex.ru_pii import (validate_inn, validate_luhn, validate_ogrn,
                                validate_snils)
    rng = random.Random(SEED + 1)
    checks = {"snils": [], "inn10": [], "inn12": [], "card": [], "ogrn": []}
    for _ in range(200):
        checks["snils"].append(validate_snils(mk_snils(rng)))
        checks["inn10"].append(validate_inn(mk_inn10(rng)))
        checks["inn12"].append(validate_inn(mk_inn12(rng)))
        checks["card"].append(validate_luhn(mk_card(rng)))
        checks["ogrn"].append(validate_ogrn(mk_ogrn(rng)))
    return {k: {"n": len(v), "engine_validator_pass": sum(v)} for k, v in checks.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=DEFAULT_N)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--verify", action="store_true",
                    help="check generated IDs against the engine validators")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    messages = build(args.n, args.seed)

    lines = [json.dumps(m, ensure_ascii=False, sort_keys=True) for m in messages]
    blob = ("\n".join(lines) + "\n").encode("utf-8")
    (out / "corpus.jsonl").write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()
    (out / "corpus.sha256").write_text(f"{digest}  corpus.jsonl\n", encoding="utf-8")

    lengths = [len(m["text"]) for m in messages]
    per_register: dict[str, dict] = {}
    for m in messages:
        entry = per_register.setdefault(m["register"], {"count": 0, "chars": 0})
        entry["count"] += 1
        entry["chars"] += len(m["text"])
    for entry in per_register.values():
        entry["mean_chars"] = round(entry["chars"] / entry["count"], 1)

    meta = {
        "file": "corpus.jsonl",
        "sha256": digest,
        "bytes": len(blob),
        "messages": len(messages),
        "seed": args.seed,
        "negative_prose_messages": NEGATIVE_PROSE,
        "registers": per_register,
        "chars": {"min": min(lengths), "p50": sorted(lengths)[len(lengths) // 2],
                  "mean": round(sum(lengths) / len(lengths), 1),
                  "max": max(lengths)},
        "provenance": ("fully synthetic, generated from the templates in "
                       "gen_corpus.py; no real-speech utterance, no transcript, "
                       "no prototype/*.json dataset, no paid corpus and no holdout "
                       "was read or copied"),
        "purpose": ("COST input for the O-DETECT isolated perf run; carries no gold "
                    "labels and supports no quality claim"),
    }
    if args.verify:
        meta["engine_validator_cross_check"] = verify()
    (out / "corpus.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"corpus.jsonl: {len(messages)} messages, {len(blob)} bytes, sha256 {digest}")
    for register, entry in sorted(per_register.items()):
        print(f"  {register:<8} n={entry['count']:<4} mean_chars={entry['mean_chars']}")
    print(f"  chars min/p50/mean/max = {meta['chars']}")
    if args.verify:
        for k, v in meta["engine_validator_cross_check"].items():
            print(f"  engine validator {k}: {v['engine_validator_pass']}/{v['n']} pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
