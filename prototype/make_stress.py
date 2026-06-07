"""STRESS benchmark — built to BREAK the detector, targeting our blind spots:
dense multi-PII, typos/OCR/unicode dashes, PII inside JSON/labeled forms,
adversarial collisions, quasi-identifiers (no direct PII but identifying),
mixed RU/EN, and heavy hard-negatives. Generated INDEPENDENTLY; NOT tuned against.

Labels:
  entities  = direct personal data that SHOULD be masked
  quasi     = quasi-identifiers (year/city/diagnosis) — a known gap, reported apart
  negatives = non-PII numbers/words that must NOT be masked
"""

import json
import random
import sys

from make_dirty import NAMES, card, date_num, email, inn, passport, phone, snils

random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
_OUT = sys.argv[1] if len(sys.argv) > 1 else "stress.json"


def _d(n: int) -> str:
    return "".join(random.choice("0123456789") for _ in range(n))


def track() -> str:
    return random.choice([f"RA{_d(9)}RU", f"{_d(14)}", f"EE{_d(9)}RU"])


def order() -> str:
    return random.choice([f"{_d(8)}", f"{_d(7)}-{_d(4)}", f"9{_d(9)}"])  # last collides w/ bare phone


def article() -> str:
    return random.choice([f"арт.{_d(6)}", f"SKU-{_d(5)}", f"{_d(3)}gb"])


def _name() -> str:
    return random.choice(NAMES)


def _typo_phone() -> str:
    p = phone()
    return random.choice([
        p.replace("0", "О", 1),                 # Cyrillic O instead of 0 (OCR)
        p.replace("-", "–"),               # en-dash instead of hyphen
        p[:4] + " " + p[4:],                     # stray space
    ])


def build() -> dict[str, object]:
    r = random.random()
    # --- 25% dense multi-PII ---
    if r < 0.25:
        n, p, s, c = _name(), phone(), snils(), card()
        return _c(f"Я {n}, тел {p}, СНИЛС {s}, оплата картой {c}. Оформите заказ.",
                  [("NAME", n.split()[-1]), ("PHONE", p), ("SNILS", s), ("CARD", c)])
    # --- 15% PII inside JSON / labeled form ---
    if r < 0.40:
        n, p, i = _name(), phone(), inn()
        fmt = random.choice([
            (f'{{"имя":"{n}","телефон":"{p}","инн":"{i}"}}', None),
            (f"ФИО: {n}\nТелефон: {p}\nИНН: {i}", None),
        ])
        return _c(fmt[0], [("NAME", n.split()[-1]), ("PHONE", p), ("INN", i)])
    # --- 15% typo / OCR / unicode dashes ---
    if r < 0.55:
        tp = _typo_phone()
        return _c(f"Не дозвониться, мой номер {tp}, перезвоните.", [("PHONE", tp)])
    # --- 12% adversarial collisions (no-PII numbers that look like PII) ---
    if r < 0.67:
        o = order()
        return _c(f"Где мой заказ {o}? Доставка задерживается.", [], [o])
    # --- 10% quasi-identifiers only (no direct PII) ---
    if r < 0.77:
        year = random.randint(1950, 2005)
        city = random.choice(["Москве", "Казани", "Сочи", "Перми"])
        diag = random.choice(["сахарный диабет", "гипертония", "астма"])
        return _c(f"Мужчина {year} года рождения, проживает в {city}, диагноз {diag}.",
                  [], [], [("QUASI", str(year)), ("QUASI", city), ("QUASI", diag)])
    # --- 13% heavy hard-negatives (no PII) ---
    if r < 0.90:
        kind = random.choice([track(), article(), f"сумма {_d(4)} р", f"IMEI {_d(15)}", f"лицевой счёт {_d(10)}"])
        return _c(f"Вопрос по {kind} — когда решится?", [], [kind.split()[-1]])
    # --- 10% mixed RU/EN + lowercase ---
    if r < 0.95:
        return _c(f"клиент ivan petrov, phone +7{_d(10)}, надо записать",
                  [("NAME", "ivan petrov")])
    # --- 5% PII split look-alike: passport & inn adjacent (both 10-12 digits) ---
    pp, i = passport(), inn()
    return _c(f"Паспорт {pp}, ИНН {i}, проверьте обе записи.",
              [("PASSPORT", pp), ("INN", i)])


def _c(text: str, entities: list, negatives: list = None, quasi: list = None) -> dict[str, object]:
    return {
        "text": text,
        "entities": [{"type": t, "value": v} for t, v in entities],
        "negatives": list(negatives or []),
        "quasi": [{"type": t, "value": v} for t, v in (quasi or [])],
    }


def main() -> None:
    cases = [build() for _ in range(600)]
    with open(_OUT, "w", encoding="utf-8") as h:
        json.dump(cases, h, ensure_ascii=False, indent=2)
    cov: dict[str, int] = {}
    negs = quasi = nopii = 0
    for case in cases:
        if not case["entities"]:
            nopii += 1
        for e in case["entities"]:
            cov[e["type"]] = cov.get(e["type"], 0) + 1
        negs += len(case["negatives"])
        quasi += len(case["quasi"])
    print(f"wrote {len(cases)} stress cases | PII: {cov}")
    print(f"no-direct-PII cases: {nopii} | hard-negatives: {negs} | quasi-identifiers: {quasi}")


if __name__ == "__main__":
    main()
