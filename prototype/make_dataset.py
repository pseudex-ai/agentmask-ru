"""Generate 100 synthetic RU golden cases with checksum-valid PII and ground truth.

No public all-types RU PII dataset exists (see research), so we synthesize one:
realistic Russian sentences, valid СНИЛС/ИНН/card checksums, with labeled spans.
"""

import json
import random

from pseudex.ru_pii import validate_luhn

random.seed(42)

NAMES = [
    "Иван Петров", "Анна Смирнова", "Сергей Иванов", "Мария Кузнецова",
    "Дмитрий Соколов", "Елена Попова", "Алексей Волков", "Ольга Новикова",
    "Андрей Морозов", "Татьяна Васильева", "Николай Зайцев", "Светлана Орлова",
]
CITIES = ["Москве", "Санкт-Петербурге", "Казани", "Новосибирске", "Екатеринбурге"]
STREETS = ["улице Ленина", "проспекте Мира", "улице Гагарина", "Тверской улице"]


def gen_phone() -> str:
    body = "".join(random.choice("0123456789") for _ in range(10))
    return random.choice([
        f"+7{body}",
        f"8{body}",
        f"+7 {body[:3]} {body[3:6]}-{body[6:8]}-{body[8:]}",
        f"8({body[:3]}){body[3:6]}-{body[6:8]}-{body[8:]}",
    ])


def gen_email() -> str:
    user = "".join(random.choice("abcdefghijklmnop") for _ in range(6))
    return f"{user}@{random.choice(['mail.ru', 'gmail.com', 'yandex.ru', 'example.ru'])}"


def gen_snils() -> str:
    base = [random.randint(0, 9) for _ in range(9)]
    total = sum(n * (9 - i) for i, n in enumerate(base))
    if total < 100:
        control = total
    elif total in (100, 101):
        control = 0
    else:
        control = total % 101
        if control == 100:
            control = 0
    text = "".join(map(str, base))
    return f"{text[:3]}-{text[3:6]}-{text[6:9]} {control:02d}"


def gen_inn10() -> str:
    base = [random.randint(0, 9) for _ in range(9)]
    weights = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    control = sum(base[i] * weights[i] for i in range(9)) % 11 % 10
    return "".join(map(str, base)) + str(control)


def gen_card() -> str:
    base = [4] + [random.randint(0, 9) for _ in range(14)]
    for check in range(10):
        number = "".join(map(str, base)) + str(check)
        if validate_luhn(number):
            return f"{number[:4]} {number[4:8]} {number[8:12]} {number[12:]}"
    raise RuntimeError("unreachable: a luhn check digit always exists")


def gen_passport() -> str:
    return f"{random.randint(10, 99)} {random.randint(10, 99)} {random.randint(100000, 999999)}"


def gen_date() -> str:
    return f"{random.randint(1, 28):02d}.{random.randint(1, 12):02d}.{random.randint(1960, 2005)}"


def build_case() -> tuple[str, list[tuple[str, str]]]:
    name, phone, email = random.choice(NAMES), gen_phone(), gen_email()
    city, street = random.choice(CITIES), random.choice(STREETS)
    snils, inn, card = gen_snils(), gen_inn10(), gen_card()
    passport, date = gen_passport(), gen_date()
    templates: list[tuple[str, list[tuple[str, str]]]] = [
        (f"Здравствуйте, меня зовут {name}, мой телефон {phone}. Найдите заказ.",
         [("NAME", name), ("PHONE", phone)]),
        (f"СНИЛС {snils}, ИНН {inn}, проверьте начисления.",
         [("SNILS", snils), ("INN", inn)]),
        # ДАТА РОЖДЕНИЯ — ЭТО DOB, А НЕ «ДАТА». Метка стояла с тех пор, когда
        # типа DOB не существовало. «Реквизиты: …, дата {date}» — тоже DOB, а не
        # DATE: СНИЛС и карта рядом делают дату персональной (правило «any
        # identifier nearby» в context._date_is_personal), и движок переводит её
        # в DOB. Голая дата БЕЗ идентификатора рядом персональными данными не
        # является — такой случай в эталоне не числится, его держит make_dirty.py.
        (f"Оплата картой {card}, дата рождения {date}.",
         [("CARD", card), ("DOB", date)]),
        (f"{name} проживает в {city} на {street}, телефон {phone}, почта {email}.",
         [("NAME", name), ("LOC", city), ("LOC", street), ("PHONE", phone), ("EMAIL", email)]),
        (f"Паспорт {passport}, выдан отделом, контакт {phone}.",
         [("PASSPORT", passport), ("PHONE", phone)]),
        (f"Клиент {name}, email {email}, ИНН {inn}, оформите доступ.",
         [("NAME", name), ("EMAIL", email), ("INN", inn)]),
        (f"Заказ на {name}, телефон {phone}, адрес: {city}, {street}.",
         [("NAME", name), ("PHONE", phone), ("LOC", city), ("LOC", street)]),
        (f"Реквизиты: СНИЛС {snils}, карта {card}, дата {date}.",
         [("SNILS", snils), ("CARD", card), ("DOB", date)]),
    ]
    return random.choice(templates)


def main() -> None:
    cases: list[dict[str, object]] = []
    for _ in range(100):
        text, entities = build_case()
        cases.append({"text": text, "entities": [{"type": t, "value": v} for t, v in entities]})
    with open("dataset.json", "w", encoding="utf-8") as handle:
        json.dump(cases, handle, ensure_ascii=False, indent=2)
    coverage: dict[str, int] = {}
    for case in cases:
        for entity in case["entities"]:
            coverage[entity["type"]] = coverage.get(entity["type"], 0) + 1
    print(f"wrote {len(cases)} cases. entity coverage: {coverage}")


if __name__ == "__main__":
    main()
