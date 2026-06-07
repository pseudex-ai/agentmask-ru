"""A LARGE, diverse, realistic HOLD-OUT benchmark — generated INDEPENDENTLY of the
detector and NOT tuned against it. Includes many intents and tool types, both
PII-carrying and NON-PII (track/order/article/currency/city-as-place), so the
eval honestly measures over-masking, not just recall.

Ground truth labels ONLY actual personal data. Non-PII numbers/words go in
`negatives` (must NOT be masked). A standalone city used as a place reference is
NOT personal data — labeled as a negative on purpose (this is a hard, honest case).
"""

import json
import random
import sys

from make_dirty import (
    NAME_HARD, NAME_OBLIQUE, NAMES,
    card, date_num, email, inn, passport, phone, snils,
)

_OUT = sys.argv[1] if len(sys.argv) > 1 else "holdout.json"
random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 2025)

CITIES = ["Москве", "Санкт-Петербурге", "Казани", "Екатеринбурге", "Новосибирске", "Сочи"]
STREETS_MARKED = ["улице Ленина", "проспекте Мира", "ул. Гагарина", "переулке Тихом"]
STREETS_BARE = ["Ленина 5 кв 3", "Пушкина 10 кв 47", "Советская 8 дом 2"]
CURRENCIES = ["USD/RUB", "EUR/RUB", "долларов в рублях", "юаня к рублю"]
PRODUCTS = ["айфон 15", "пылесос Dyson", "кроссовки найк", "телевизор 55 дюймов"]


def _d(n: int) -> str:
    return "".join(random.choice("0123456789") for _ in range(n))


def track_no() -> str:
    return random.choice([f"RA{_d(9)}RU", f"8009{_d(10)}", f"{_d(14)}"])


def order_no() -> str:
    return random.choice([f"{_d(8)}", f"{_d(8)}-{_d(4)}", f"№{_d(7)}"])


def article() -> str:
    return random.choice([f"арт. {_d(6)}", f"ART-{_d(5)}", f"{_d(3)}gb", f"SKU{_d(5)}"])


def sum_rub() -> str:
    return random.choice([f"{_d(4)} р", f"{random.randint(1, 50)}000 рублей", f"{_d(3)}99 ₽"])


def imei() -> str:
    return _d(15)


def name_any() -> str:
    return random.choice(NAMES + NAME_OBLIQUE + NAME_HARD)


def _name_val(n: str) -> str:
    return n.split()[-1] if " " in n else n


def build() -> dict[str, object]:
    r = random.random()
    # ---- PII-carrying tasks ----
    if r < 0.10:
        p = phone()
        return _case(f"Не пришёл заказ, мой телефон {p}, проверьте статус.", [("PHONE", p)])
    if r < 0.18:
        n, p, d = name_any(), phone(), date_num()
        return _case(f"Запишите на стрижку {n}, тел {p}, на {d}.",
                     [("NAME", _name_val(n)), ("PHONE", p), ("DATE", d)])
    if r < 0.25:
        n, s, d = random.choice(NAMES), snils(), date_num()
        return _case(f"Запишите к врачу: {n}, СНИЛС {s}, дата рождения {d}.",
                     [("NAME", _name_val(n)), ("SNILS", s), ("DATE", d)])
    if r < 0.31:
        c = card()
        return _case(f"Верните деньги на карту {c}.", [("CARD", c)])
    if r < 0.37:
        i = inn()
        return _case(f"Проверьте контрагента, ИНН {i}.", [("INN", i)])
    if r < 0.42:
        pp = passport()
        return _case(f"Подтвердите личность, паспорт {pp}.", [("PASSPORT", pp)])
    if r < 0.48:
        a = random.choice(STREETS_MARKED + STREETS_BARE)
        return _case(f"Оформите доставку: {a}.", [("LOC", a)])
    if r < 0.53:
        e = email()
        return _case(f"Найдите профиль по почте {e}.", [("EMAIL", e)])
    if r < 0.58:
        n, p = random.choice(NAMES), phone()
        return _case(f"Забыл вещь в такси, я {n}, перезвоните на {p}.",
                     [("NAME", _name_val(n)), ("PHONE", p)])
    # ---- NON-PII tasks (must NOT mask) ----
    if r < 0.66:
        t = track_no()
        return _case(f"Где посылка, трек {t}, когда доставят?", [], [t])
    if r < 0.73:
        o = order_no()
        return _case(f"Уточните статус заказа {o}.", [], [o])
    if r < 0.79:
        a = article()
        return _case(f"Есть ли в наличии {random.choice(PRODUCTS)}, {a}?", [], [a])
    if r < 0.84:
        cur = random.choice(CURRENCIES)
        return _case(f"Какой курс {cur} сегодня?", [], [])
    if r < 0.89:
        city = random.choice(CITIES)
        return _case(f"Подскажите часы работы магазина в {city}?", [], [city])
    if r < 0.93:
        s = sum_rub()
        return _case(f"Почему списали {s}, верните пожалуйста.", [], [s.split()[0]])
    # ---- MIXED: PII + non-PII in one message ----
    if r < 0.97:
        p, o = phone(), order_no()
        return _case(f"Заказ {o} не пришёл, мой телефон {p}.", [("PHONE", p)], [o])
    c, o = card(), order_no()
    return _case(f"Оплатил картой {c} заказ {o}, деньги списались дважды.",
                 [("CARD", c)], [o])


def _case(text: str, entities: list, negatives: list = None) -> dict[str, object]:
    return {
        "text": text,
        "entities": [{"type": t, "value": v} for t, v in entities],
        "negatives": [n for n in (negatives or [])],
    }


def main() -> None:
    cases = [build() for _ in range(320)]
    with open(_OUT, "w", encoding="utf-8") as handle:
        json.dump(cases, handle, ensure_ascii=False, indent=2)
    cov: dict[str, int] = {}
    negs = no_pii = 0
    for case in cases:
        if not case["entities"]:
            no_pii += 1
        for e in case["entities"]:
            cov[e["type"]] = cov.get(e["type"], 0) + 1
        negs += len(case["negatives"])
    print(f"wrote {len(cases)} cases | PII coverage: {cov}")
    print(f"non-PII (no entities) cases: {no_pii} | hard-negative items: {negs}")


if __name__ == "__main__":
    main()
