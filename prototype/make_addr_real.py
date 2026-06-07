"""A RICH, realistic RU ADDRESS benchmark — built INDEPENDENTLY of the detector
(composed from real address components, 8 write-orders, embedded in real agent
tasks). Seed is a CLI arg so we validate on FRESH seeds, never tuning to one set.

Ground truth labels the address as LOC. Non-address numbers/words go to
`negatives` (must NOT be masked). Pure hard-negative cases (square-meters,
versions, city-as-place, order/track) measure over-masking honestly.

Usage: python make_addr_real.py <out.json> <seed>
"""

import json
import random
import sys

CITIES = ["Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Новосибирск",
          "Нижний Новгород", "Самара", "Ростов-на-Дону", "Уфа", "Краснодар",
          "Воронеж", "Пермь", "Волгоград", "Сочи", "Тюмень", "Омск", "Челябинск"]
CITY_PREFIX = ["г. ", "г ", "город ", ""]
SETTLEMENTS = ["пос. Сосновый", "посёлок Лесной", "село Ивановка", "д. Петрово",
               "пгт Развилка", "ст. Динская", "хутор Весёлый", "с. Берёзовка"]
STREET_TYPES = {
    "улица": ["улица", "ул.", "ул"],
    "проспект": ["проспект", "пр-т", "пр-кт", "просп.", "пр."],
    "переулок": ["переулок", "пер."],
    "проезд": ["проезд", "пр-д"],
    "бульвар": ["бульвар", "б-р"],
    "набережная": ["набережная", "наб."],
    "шоссе": ["шоссе", "ш."],
    "площадь": ["площадь", "пл."],
    "тупик": ["тупик", "туп."],
    "аллея": ["аллея"],
    "линия": ["линия"],
}
NAMES_SURN = ["Ленина", "Гагарина", "Пушкина", "Кирова", "Жукова", "Чехова",
              "Толстого", "Гоголя", "Лермонтова", "Маяковского", "Циолковского"]
NAMES_ADJ = ["Советская", "Садовая", "Центральная", "Лесная", "Молодёжная",
             "Северная", "Южная", "Заречная", "Школьная", "Луговая", "Полевая",
             "Зелёная", "Первомайская", "Солнечная", "Новая"]
NAMES_GEN = ["Мира", "Победы", "Октября", "Космонавтов", "Строителей", "Дружбы",
             "Свободы", "Труда"]
NAMES_NUM = ["8 Марта", "9 Мая", "1905 года", "2-я Парковая", "26 Бакинских Комиссаров"]
NAMES_MULTI = ["Карла Маркса", "Розы Люксембург", "Миклухо-Маклая", "Академика Сахарова"]
ALL_NAMES = NAMES_SURN + NAMES_ADJ + NAMES_GEN + NAMES_NUM + NAMES_MULTI

TASKS = [
    "Оформите доставку по адресу: {a}.",
    "Курьер должен приехать на {a}.",
    "Запишите адрес клиента: {a}.",
    "Я живу по адресу {a}, заберите вещи.",
    "Адрес офиса для встречи — {a}.",
    "Доставьте заказ на {a}, оплата при получении.",
    "Привезите цветы на {a} к 18:00.",
    "Подключите интернет по адресу {a}.",
    "Вызовите сантехника на {a}.",
    "Отправьте посылку получателю: {a}.",
]


def _house_num() -> str:
    n = random.randint(1, 250)
    tail = random.choice(["", "", random.choice("АБВГ"), f"/{random.randint(1, 9)}"])
    return f"{n}{tail}"


def _house(marked: bool) -> str:
    num = _house_num()
    body = (random.choice(["д. ", "дом ", "д.", "д "]) + num) if marked else num
    if random.random() < 0.3:
        body += random.choice([" к. ", " корп. ", " к", " корп "]) + str(random.randint(1, 6))
    if random.random() < 0.15:
        body += random.choice([" стр. ", " стр.", " строение "]) + str(random.randint(1, 4))
    return body


def _apt() -> str:
    m = random.choice(["кв. ", "кв.", "кв ", "квартира ", "оф. ", "офис ", "пом. "])
    return m + str(random.randint(1, 400))


def _street_type(key: str) -> str:
    return random.choice(STREET_TYPES[key])


def _address() -> str:
    name = random.choice(ALL_NAMES)
    stype = random.choice(list(STREET_TYPES))
    order = random.random()
    city = random.choice(CITY_PREFIX) + random.choice(CITIES)

    if order < 0.18:  # canonical full (with index sometimes)
        idx = f"{random.randint(100000, 699999)}, " if random.random() < 0.5 else ""
        return f"{idx}{city}, {_street_type(stype)} {name}, {_house(True)}, {_apt()}"
    if order < 0.34:  # city + street + house
        return f"{city}, {_street_type(stype)} {name}, {_house(True)}"
    if order < 0.46:  # marker-last street
        return f"{name} {_street_type(stype)}, {_house(True)}"
    if order < 0.60:  # marker-less anchored (name + bare house, + apt)
        return f"{name} {_house_num()}, {_apt()}"
    if order < 0.70:  # pure marker-less (HARDEST)
        return f"{name} {_house_num()}"
    if order < 0.80:  # микрорайон
        mk = random.choice(["мкр ", "мкр. ", "микрорайон ", "мкрн "])
        return f"{mk}{random.choice(NAMES_ADJ)}, {_house(True)}, {_apt()}"
    if order < 0.90:  # settlement
        return f"{random.choice(SETTLEMENTS)}, {_street_type(stype)} {name}, {_house(True)}"
    # compact, abbreviations glued
    return f"{random.choice(['ул.', 'пр-т', 'пер.'])}{name} д{_house_num()} {random.choice(['кв', 'кв.'])}{random.randint(1, 200)}"


def _d(n: int) -> str:
    return "".join(random.choice("0123456789") for _ in range(n))


# Pure non-address hard negatives (must NOT be masked as LOC).
NEG_TASKS = [
    ("Площадь помещения {n} кв.м, какая цена?", lambda: str(random.randint(20, 120))),
    ("Купил {n} кв.м плитки, посчитайте смету.", lambda: str(random.randint(5, 80))),
    ("Обновите Windows {n} и драйверы.", lambda: random.choice(["10", "11"])),
    ("Поставьте Python 3.{n}, нужно для проекта.", lambda: str(random.randint(8, 13))),
    ("Согласно статье {n} ФЗ оформите согласие.", lambda: str(random.randint(1, 200))),
    ("Курс доллара {n} рублей сегодня?", lambda: str(random.randint(80, 99))),
    ("Магазин в {n} работает до 22:00?", lambda: random.choice(CITIES)),
    ("Где заказ {n}? Доставка задерживается.", lambda: _d(8)),
    ("Трек RA{n}RU когда придёт?", lambda: _d(9)),
    ("Встреча в переговорной {n} в 15:00.", lambda: str(random.randint(1, 9))),
    ("На складе осталось {n} шт, и т.д.", lambda: str(random.randint(2, 50))),
    ("Этаж {n}, лифт не работает, почините.", lambda: str(random.randint(2, 25))),
]


def build() -> dict[str, object]:
    if random.random() < 0.68:  # address-carrying
        a = _address()
        task = random.choice(TASKS)
        return {"text": task.format(a=a),
                "entities": [{"type": "LOC", "value": a}], "negatives": []}
    tmpl, gen = random.choice(NEG_TASKS)
    val = gen()
    return {"text": tmpl.format(n=val),
            "entities": [], "negatives": [val if val not in CITIES else val]}


def realistic_address() -> str:
    """Public entry for other harnesses (e.g. live_eval) — one rich RU address."""
    return _address()


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "addr_real.json"
    random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 7)
    cases = [build() for _ in range(350)]
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(cases, handle, ensure_ascii=False, indent=2)
    loc = sum(1 for c in cases if c["entities"])
    print(f"wrote {len(cases)} cases | LOC-carrying: {loc} | non-address: {len(cases) - loc}")


if __name__ == "__main__":
    main()
