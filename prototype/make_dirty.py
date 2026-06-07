"""Build a DIRTY, realistic RU dataset from the researched patterns:
messy PII formats (incl. bare phones, no-dash СНИЛС, free-form addresses,
oblique/Latin names, DOB-as-words) mixed with HARD NEGATIVES (track/order/
sum/article numbers that must NOT be masked). Ground truth = only real PII.
"""

import json
import random

random.seed(13)

NAMES = ["Иван Петров", "Анна Смирнова", "Сергей Иванов", "Мария Кузнецова", "Дмитрий Соколов"]
NAME_OBLIQUE = ["на Ивана", "для Анны Петровой", "записан как Сергей", "клиент Мария Кузнецова"]
NAME_HARD = ["Ivan Petrov", "света", "Сидоров И.И."]  # Latin / diminutive / initials — NER-hard
ADDR_MARKED = ["улице Гагарина дом 7", "проспекте Мира, дом 5", "ул. Ленина д 12"]
ADDR_FREEFORM = ["Ленина 5 кв 3", "мкр Северный д12 кв 8"]  # no marker -> hard


def _digits9() -> str:
    # RU mobile without country code = 10 digits starting with 9.
    return "9" + "".join(random.choice("0123456789") for _ in range(9))


def phone() -> str:
    b = _digits9()
    return random.choice([
        f"+7{b}", f"8{b}", f"8 {b[:3]} {b[3:6]} {b[6:8]} {b[8:]}",
        f"8-{b[:3]}-{b[3:6]}-{b[6:8]}-{b[8:]}", f"+7 ({b[:3]}) {b[3:6]}-{b[6:8]}-{b[8:]}",
        b,  # bare mobile, no country code -> current regex misses this
    ])


def snils() -> str:
    base = [random.randint(0, 9) for _ in range(9)]
    total = sum(n * (9 - i) for i, n in enumerate(base))
    c = total if total < 100 else (0 if total in (100, 101) else (0 if total % 101 == 100 else total % 101))
    s = "".join(map(str, base))
    return random.choice([f"{s[:3]}-{s[3:6]}-{s[6:9]} {c:02d}", f"{s}{c:02d}"])  # dashed / no-dash


def inn() -> str:
    base = [random.randint(0, 9) for _ in range(9)]
    w = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    c = sum(base[i] * w[i] for i in range(9)) % 11 % 10
    return "".join(map(str, base)) + str(c)


def card() -> str:
    while True:
        d = [4] + [random.randint(0, 9) for _ in range(14)]
        for chk in range(10):
            num = "".join(map(str, d)) + str(chk)
            ok = (sum((int(x) * 2 - 9 if (i % 2 == 1 and int(x) * 2 > 9) else int(x) * 2 if i % 2 == 1 else int(x))
                      for i, x in enumerate(reversed(num))) % 10 == 0)
            if ok:
                return random.choice([f"{num[:4]} {num[4:8]} {num[8:12]} {num[12:]}", num])


def passport() -> str:
    a, b, c = random.randint(10, 99), random.randint(10, 99), random.randint(100000, 999999)
    return random.choice([f"{a}{b} {c}", f"{a} {b} {c}", f"{a}{b}{c}"])


def email() -> str:
    return "".join(random.choice("abcdefghij") for _ in range(6)) + "@mail.ru"


def date_num() -> str:
    return f"{random.randint(1, 28):02d}.{random.randint(1, 12):02d}.{random.randint(1960, 2005)}"


# Hard negatives: must NOT be masked.
HARD_NEG = [
    "RA123456789RU", "80098765432109", "52905115-0017", "0123456789",
    "артикул 256gb", "сумма 4990 р", "талон 778-2034", "чек №35417",
]


def build() -> dict[str, object]:
    kind = random.random()
    ents: list[tuple[str, str]] = []
    negs: list[str] = []
    if kind < 0.20:
        p = phone(); ents = [("PHONE", p)]
        text = f"Не пришёл заказ, мой {p}, проверьте статус."
    elif kind < 0.32:
        s = snils(); ents = [("SNILS", s)]
        text = f"Проверьте начисления, снилс {s}."
    elif kind < 0.44:
        i = inn(); ents = [("INN", i)]
        text = f"Контрагент инн {i}, проверьте."
    elif kind < 0.54:
        c = card(); ents = [("CARD", c)]
        text = f"Верните деньги на карту {c}."
    elif kind < 0.62:
        pp = passport(); ents = [("PASSPORT", pp)]
        text = f"Паспорт {pp}, оформите."
    elif kind < 0.72:
        n = random.choice(NAMES + NAME_OBLIQUE); p = phone()
        ents = [("NAME", n.split()[-1] if " " in n else n), ("PHONE", p)]
        text = f"Запишите {n}, тел {p}, на завтра."
    elif kind < 0.80:
        n = random.choice(NAME_HARD); ents = [("NAME", n)]
        text = f"Оформите заказ, имя {n}."
    elif kind < 0.88:
        a = random.choice(ADDR_MARKED + ADDR_FREEFORM); ents = [("LOC", a)]
        text = f"Доставьте на {a}."
    elif kind < 0.94:
        d = date_num(); ents = [("DATE", d)]
        text = f"Дата рождения {d}, проверьте полис."
    else:
        neg = random.choice(HARD_NEG); negs = [neg.split()[-1]]
        text = f"Уточните, {neg} — когда будет готово?"
    return {"text": text, "entities": [{"type": t, "value": v} for t, v in ents], "negatives": negs}


def main() -> None:
    cases = [build() for _ in range(150)]
    with open("dirty.json", "w", encoding="utf-8") as handle:
        json.dump(cases, handle, ensure_ascii=False, indent=2)
    cov: dict[str, int] = {}
    negs = 0
    for case in cases:
        for entity in case["entities"]:
            cov[entity["type"]] = cov.get(entity["type"], 0) + 1
        negs += len(case["negatives"])
    print(f"wrote {len(cases)} dirty cases | PII coverage: {cov} | hard-negatives: {negs}")


if __name__ == "__main__":
    main()
