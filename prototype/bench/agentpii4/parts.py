"""Typed parts of a PII value, and the ONE splitter allowed on unknown text.

TWO DIRECTIONS, AND THEY ARE NOT SYMMETRIC.

  * The corpus builds a value from parts (`pools.Rendered.parts`) and never
    parses its own surface back — a searched ground truth is the v2 defect that
    cost 162 of 183 sloppy failures.
  * The comparator meets strings it did not build: the substitute the model
    read, and what the model wrote into a tool field. Those HAVE to be split,
    and `parts_of` is the only place that does it. It is written here, in the
    benchmark, and never imported from `pseudex/`: the engine's own splitter
    deciding whether the engine's parts match would be the instrument judging
    itself.
"""
import re

from bench.agentpii3.schema import _address_parts, digits_of

Parts = dict[str, str]

# Nominative AND oblique: a substitute reaches the model inflected («Льва
# Евгеньевича») and the model may copy it as read.
_PATRONYMIC_TAIL = re.compile(
    r"(?:(?:ович|евич|ич|ыч)(?:а|у|ем|е)?|(?:овна|евна|ична|инична|вна)|(?:овн|евн|ичн|иничн)(?:ы|е|у|ой))$",
    re.IGNORECASE)
_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_DATE_RU = re.compile(r"(\d{1,2})[./ ](\d{1,2})[./ ](\d{4})")
_EMAIL = re.compile(r"([^@\s]+)@([^@\s]+)")
_PLATE = re.compile(r"([АВЕКМНОРСТУХавекмнорстух])\s*(\d{3})\s*([АВЕКМНОРСТУХавекмнорстух]{2})\s*(\d{2,3})")


def name_parts(surface: str) -> Parts:
    """surname / given / patronymic from a written name, by SHAPE only.

    A patronymic is the word with the patronymic suffix; of the remaining
    words the one ending in a surname-like suffix (-ов/-ев/-ин/-ая/-ова...) is
    the surname when there are two, else word order decides (surname first is
    the Russian document order, and what a CRM field expects). No morphology,
    no dictionary: this is a benchmark-side reading of an unknown string, and
    it must be wrong the same way for both arms.
    """
    words = [word.strip(".,;:«»\"'()") for word in surface.split()]
    words = [word for word in words if word]
    out: Parts = {}
    rest: list[str] = []
    for word in words:
        if "patronymic" not in out and _PATRONYMIC_TAIL.search(word) and len(word) > 4:
            out["patronymic"] = word
        else:
            rest.append(word)
    if len(rest) == 1:
        out["surname" if _surname_shaped(rest[0]) and not _given_name(rest[0]) else "given"] = rest[0]
    elif len(rest) >= 2:
        first, second = rest[0], rest[1]
        # A GIVEN NAME MAY WEAR A SURNAME'S SUFFIX — «Ирина», «Марина», «Яков»,
        # «Ян» — and by shape alone both words of «Ирина Лебедева» are surnames,
        # so document order made «Ирина» the surname. The scripted agent then
        # wrote the cardholder as «LEBEDEVA IRINA» for the substitute while
        # writing «NATALIA NOVIKOVA» for the real name: seven divergences on
        # 474 cases that were the instrument's, not the engine's. A model knows
        # which of two words is a name; so does this list, which is the
        # instrument's own and never the engine's pool. Shape still decides
        # whenever it is unambiguous.
        first_given, second_given = _given_name(first), _given_name(second)
        if first_given and not second_given:
            out["given"], out["surname"] = first, second
        elif second_given and not first_given:
            out["surname"], out["given"] = first, second
        elif _surname_shaped(second) and not _surname_shaped(first):
            out["given"], out["surname"] = first, second
        else:
            out["surname"], out["given"] = first, second
    return out


# Common Russian given names — the tie-breaker above. Generic, both genders,
# the everyday top of the frequency lists; NOT the engine's substitute pool.
_GIVEN_NAMES: frozenset[str] = frozenset(name.lower() for name in (
    "Александр Алексей Анатолий Андрей Антон Аркадий Арсений Артём Артем Борис Вадим Валентин "
    "Валерий Василий Вениамин Виктор Виталий Владимир Владислав Всеволод Вячеслав Геннадий "
    "Георгий Герман Глеб Григорий Даниил Данила Демьян Денис Дмитрий Евгений Егор Захар Иван "
    "Игнат Игорь Илья Кирилл Константин Лев Леонид Макар Максим Марк Матвей Михаил Никита "
    "Николай Олег Павел Пётр Петр Платон Радислав Роман Руслан Савва Семён Семен Сергей Станислав "
    "Степан Тарас Тимофей Тимур Фёдор Федор Филипп Харитон Эдуард Юлиан Юрий Яков Ян Ярослав "
    "Остап Родион Трофим Игнатий Гавриил Елисей Мирон Прохор Савелий Тихон Лука Назар "
    "Александра Алевтина Алина Алиса Алла Альбина Анастасия Ангелина Анна Антонина Арина "
    "Белла Валентина Валерия Варвара Вера Вероника Виктория Галина Гелена Дарья Диана Дина Ева "
    "Евгения Екатерина Елена Елизавета Жанна Зинаида Зоя Иванна Инна Ирина Капитолина Карина "
    "Кира Клавдия Кристина Ксения Лариса Лидия Лилия Любовь Людмила Маргарита Марина Мария "
    "Марта Милана Надежда Наталия Наталья Нина Оксана Олеся Ольга Полина Раиса Регина Римма "
    "Сабина София Софья Стелла Таисия Тамара Татьяна Ульяна Фаина Христина Эвелина Эмилия Юлия "
    "Яна Ярослава Николь Агата Аглая Злата Мирослава Пелагея Серафима Устинья"
).split())


def _given_name(word: str) -> bool:
    return word.lower().replace("ё", "е") in _GIVEN_NAMES or word.lower() in _GIVEN_NAMES


def _surname_shaped(word: str) -> bool:
    low = word.lower()
    return low.endswith(("ов", "ев", "ин", "ын", "ова", "ева", "ина", "ына",
                         "ский", "ская", "цкий", "цкая", "ых", "их", "ко", "ук",
                         "юк", "ян", "дзе", "швили"))


def address_parts(surface: str) -> Parts:
    """street / house / flat / entrance / building / city from a written address.

    `_address_parts` (benchmark schema, not the engine) does the marker-aware
    split with spoken numerals resolved to digits. A leading capitalised word
    followed by a comma is a city.
    """
    # «129кв212»: the sloppy register glues the flat marker to the house, and
    # the engine mints the substitute in the same shape; a splitter that
    # needed a space wrote no flat at all.
    surface = re.sub(r"(\d)(кв|кв\.)(\d)", r"\1 \2 \3", surface)
    parts = dict(_address_parts(surface))
    city = re.match(r"^\s*([А-ЯЁ][а-яё\-]+),\s", surface)
    if city:
        parts["city"] = city.group(1).lower()
        if "street" in parts:
            parts["street"] = " ".join(
                word for word in parts["street"].split() if word != city.group(1).lower())
    elif "street" in parts:
        # A lower-case settlement in front of a type word («глазов проезд
        # Сиреневый»): the type word marks where the street begins.
        words = parts["street"].split()
        if len(words) >= 3 and _STREET_TYPE.fullmatch(words[1]):
            parts["city"] = words[0]
            parts["street"] = " ".join(words[1:])
    return parts


_STREET_TYPE = re.compile(r"(?i)(?:ул\.?|улица|улицу|улице|пр-т|пр\.?|проспект\w*|пер\.?|переулок|переулк\w*|"
                          r"б-р|бульвар\w*|ш\.?|шоссе|пл\.?|площад\w*|наб\.?|набережн\w*|проезд\w*|тупик\w*|аллея|аллее)")


def phone_parts(surface: str) -> Parts:
    digits = digits_of(surface)
    return {"digits": digits[-10:]} if len(digits) >= 10 else ({"digits": digits} if digits else {})


def passport_parts(surface: str) -> Parts:
    digits = digits_of(surface)
    if len(digits) == 10:
        return {"series": digits[:4], "number": digits[4:]}
    if len(digits) == 4:
        return {"series": digits}
    if len(digits) == 6:
        return {"number": digits}
    return {"digits": digits} if digits else {}


def dob_parts(surface: str) -> Parts:
    iso = _DATE_ISO.search(surface)
    if iso:
        return {"iso": f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"}
    ru = _DATE_RU.search(surface)
    if ru:
        return {"iso": f"{int(ru.group(3)):04d}-{int(ru.group(2)):02d}-{int(ru.group(1)):02d}"}
    return {}


def email_parts(surface: str) -> Parts:
    hit = _EMAIL.search(surface)
    return {"local": hit.group(1).lower(), "domain": hit.group(2).lower()} if hit else {}


def plate_parts(surface: str) -> Parts:
    hit = _PLATE.search(surface.replace(" ", ""))
    if not hit:
        return {}
    return {"letter": hit.group(1).upper(), "digits": hit.group(2),
            "pair": hit.group(3).upper(), "region": hit.group(4)}


def digit_parts(surface: str) -> Parts:
    digits = digits_of(surface)
    return {"digits": digits} if digits else {}


_SPLITTERS = {
    "NAME": name_parts, "LOC": address_parts, "PHONE": phone_parts,
    "PASSPORT": passport_parts, "DOB": dob_parts, "EMAIL": email_parts,
    "PLATE": plate_parts, "SNILS": digit_parts, "INN": digit_parts, "CARD": digit_parts,
}


def parts_of(kind: str, surface: str) -> Parts:
    """Split a string the benchmark did NOT build. Only for substitutes and
    model output; the corpus's own values carry their parts from birth."""
    splitter = _SPLITTERS.get(kind)
    return splitter(surface) if splitter and surface else {}


def is_part_of(candidate: str, parts: Parts) -> str:
    """Which role of `parts` the candidate equals, or ""."""
    folded = candidate.strip().casefold().replace("ё", "е")
    for role, value in parts.items():
        if role == "gender":
            continue
        if folded and folded == value.strip().casefold().replace("ё", "е"):
            return role
        if role == "house" and digits_of(candidate) and digits_of(candidate) == digits_of(value):
            return role
    return ""


def roles_covered(candidate: str, parts: Parts) -> int:
    """How many roles of `parts` appear inside the candidate string."""
    folded = candidate.casefold().replace("ё", "е")
    return sum(1 for role, value in parts.items()
               if role != "gender" and value and value.casefold().replace("ё", "е") in folded)


def main() -> int:
    checks = [
        (name_parts("Иванов Пётр Сергеевич"), {"surname": "Иванов", "given": "Пётр", "patronymic": "Сергеевич"}),
        (name_parts("Тамара Владимировна Павлова"), {"given": "Тамара", "patronymic": "Владимировна", "surname": "Павлова"}),
        (name_parts("ким виктор"), {"surname": "ким", "given": "виктор"}),
        (name_parts("Ирина Лебедева"), {"given": "Ирина", "surname": "Лебедева"}),
        (name_parts("Лебедева Ирина"), {"surname": "Лебедева", "given": "Ирина"}),
        (name_parts("Яков Осипов"), {"given": "Яков", "surname": "Осипов"}),
        (name_parts("Марина Кузнецова"), {"given": "Марина", "surname": "Кузнецова"}),
        (name_parts("Ян Рыбаков"), {"given": "Ян", "surname": "Рыбаков"}),
        (address_parts("ул. Ленина, д. 14, кв. 5"), {"street": "ленина", "house": "14", "flat": "5"}),
        (address_parts("Ижевск, улица Клубная, 85, кв. 12")["city"], "ижевск"),
        (passport_parts("4509 123456"), {"series": "4509", "number": "123456"}),
        (dob_parts("14.03.1987"), {"iso": "1987-03-14"}),
        (dob_parts("1987-03-14"), {"iso": "1987-03-14"}),
        (phone_parts("+7 (916) 402-11-87"), {"digits": "9164021187"}),
        (email_parts("Bukin@Mail.ru"), {"local": "bukin", "domain": "mail.ru"}),
        (plate_parts("а123вс18"), {"letter": "А", "digits": "123", "pair": "ВС", "region": "18"}),
        (is_part_of("4509", {"series": "4509", "number": "123456"}), "series"),
        (is_part_of("ленина", {"street": "ленина", "house": "14"}), "street"),
    ]
    failures = 0
    for got, want in checks:
        if got != want:
            failures += 1
            print(f"FAIL {got!r} != {want!r}")
    print("parts: PASS" if not failures else f"parts: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
