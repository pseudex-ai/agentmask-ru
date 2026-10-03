"""ФАЗА 4b — ПЯТЬ РЕШЕНИЙ ВЛАДЕЛЬЦА, ЗАПИСАННЫЕ УТВЕРЖДЕНИЯМИ.

Пин к `bench/edge_case_stress.py` (W1–W8). Метрика там СЧИТАЕТ и печатает
44/66; здесь те же починенные проверки ТРЕБУЮТСЯ, поэтому регрессия краснеет
детерминированно, без чтения чужого вывода, и падает ровно на тех строках,
которые трогались.

ЧТО ЗДЕСЬ ПИНИТСЯ, ПО КЛАСТЕРАМ (решения — OWNER-DECISIONS-PHASE4B.md):

  A (W1)  изменяемая часть адреса, отправленная ОТДЕЛЬНЫМ полем схемы
          (`build`, `corpus`), возвращается настоящей — и на плече аргумента,
          и на контент-плече для JSON-объекта;
  B (W2)  подмена, отчеканенная СЛОВАМИ, размаскировывается дословно: цифры
          ищет `zero_grouped`/`_dictated_place_key`, а не вторая читалка;
  C (W3, W4)  контент-плечо сворачивает регистр имени, и инициалы БЕЗ ТОЧЕК
          («Сазонов МС») разрешаются тем же разворотом, что и с точками;
  D (W5, W6)  VIN с разделителями/склеенной подсказкой и ПТС со склеенной
          подсказкой детокенизируются;
  E (W7)  ведущий ноль, снятый у группы, возвращает настоящее, а не подмену;
  A (W8)  адрес СОСТАВНОЙ: тождество (улица+дом) чеканится ОДИН раз, а
          квартира/подъезд/этаж/корпус растут на нём СВОИМИ подменами, поэтому
          два человека в одном доме различимы, а `detokenize` возвращает РОВНО
          написанное клиентом. Пин `test_identity_invariant.py` переписан вместе
          с этим: полного равенства строк там больше нет, ядро — есть.

НЕГАТИВНЫЕ КОНТРОЛИ — здесь же, потому что правило, проверенное только на том,
что находиться ДОЛЖНО, это правило, про которое неизвестно, что ещё оно находит:
два разных человека на одной улице остаются разными, разный дом форкает
подмену, чужие цифры не трогаются, подмена части НЕ равна настоящей части.

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python test_phase4b.py
"""

import re
import sys

import testkit

testkit.load_dev_bundle()

from pseudex import morph_places, redact                      # noqa: E402
from pseudex.detect_all import Detector                       # noqa: E402
from pseudex.morph_places import address_key, split_roles     # noqa: E402
from pseudex.vault import Vault, canonicalize, place_key      # noqa: E402

DETECTOR = Detector()
CUSTOMER = "phase4b-pin"
RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail else ""))


def mask(value: str, vault: Vault | None = None) -> tuple[str, Vault]:
    vault = vault or Vault(":memory:", CUSTOMER)
    return redact.mask_text(value, vault, DETECTOR.detect(value)), vault


def args(raw: str, vault: Vault) -> str:
    return redact.unmask_arguments(raw, vault)


# ======================================================================= A — W1

def w1_address_leaf() -> None:
    """Изменяемая часть отдельным полем схемы — настоящая, на обоих плечах."""
    for leg in ("args", "content"):
        vault = Vault(":memory:", CUSTOMER)
        masked, vault = mask("улица Тверитина, дом 10, квартира 7", vault)
        roles = redact.morph_places.split_roles(masked)
        payload = ('{"street": "%s", "build": "%s", "flat": "%s"}'
                   % (roles["street"].split()[-1], roles["house"], roles["flat"]))
        back = args(payload, vault) if leg == "args" else redact.unmask_text(payload, vault)
        check('"10"' in back and '"7"' in back,
              f"W1: `build`/`flat` отдельными полями ({leg})", back)

    # …и все части сразу, включая корпус: build и corpus оставались ФЕЙКОМ.
    # Улица берётся ИЗ ПОДМЕНЫ — свидетельство владельца собирается из всех
    # листьев группы, и подставленное чужое слово лишает вопрос ответа.
    vault = Vault(":memory:", CUSTOMER)
    masked, vault = mask(
        "улица Тверитина, дом 10, корпус 3, подъезд 2, этаж 5, квартира 7", vault)
    roles = redact.morph_places.split_roles(masked)
    street = roles["street"].split()[-1]
    payload = ('{"street": "%s", "build": "%s", "corpus": "%s", "flat": "%s"}'
               % (street, roles["house"], roles["building"], roles["flat"]))
    back = args(payload, vault)
    check('"10"' in back and '"3"' in back and '"7"' in back,
          "W1: `build`/`corpus`/`flat` в одном вызове", back)

    # НЕГАТИВ: поле, НЕ названное адресной ролью, не трогается вовсе.
    vault = Vault(":memory:", CUSTOMER)
    masked, vault = mask("улица Тверитина, дом 10, квартира 7", vault)
    roles = redact.morph_places.split_roles(masked)
    payload = '{"case": "%s", "quantity": 3}' % roles["flat"]
    back = args(payload, vault)
    check(roles["flat"] in back and '"quantity": 3' in back,
          "W1-негатив: `case`/`quantity` — числа заказчика, не адрес", back)


# ======================================================================= B — W2

def w2_dictated_detok() -> None:
    """Подмена словами размаскировывается дословно — и в прозе, и в аргументе."""
    real = "улица Тверитина, дом десять, квартира семь"
    vault = Vault(":memory:", CUSTOMER)
    masked, vault = mask(real, vault)
    check(re.search(r"[а-яё]{4,}", split_roles(masked).get("house", "") or "") is not None,
          "W2: подмена чеканится СЛОВАМИ (форма клиента)", masked)
    back = redact.unmask_text(masked, vault)
    check("Тверитина" in back and "десять" in back and "семь" in back,
          "W2: дословная подмена размаскирована", back)
    back_args = args('{"value": "%s"}' % masked.replace('"', "'"), vault)
    check("Тверитина" in back_args and "десять" in back_args,
          "W2: то же на плече аргумента", back_args)

    # НЕГАТИВ: число заказчика, не совпадающее ни с одной подменой, стоит как было.
    check("Тверитина" not in redact.unmask_text("дом двадцать шесть", vault),
          "W2-негатив: «дом двадцать шесть» без подмены не трогается",
          redact.unmask_text("дом двадцать шесть", vault))


# ================================================================== C — W3/W4

def w3_lowercase_name() -> None:
    """Контент-плечо разрешает имя, регистр которого свернула модель."""
    vault = Vault(":memory:", CUSTOMER)
    masked, vault = mask("Клиент Иванов Пётр Сергеевич оформил заказ", vault)
    back = redact.unmask_text(masked.lower(), vault)
    check("иванов" in back.lower() and "пётр" in back.lower()
          and "сергеевич" in back.lower(),
          "W3: строчное имя на контент-плече", back)
    # НЕГАТИВ: строчная проза без подмены не трогается.
    check(redact.unmask_text("клиент оформил заказ и ждёт", vault)
          == "клиент оформил заказ и ждёт",
          "W3-негатив: строчная проза не трогается")


def w4_squeezed_initials() -> None:
    """Инициалы без точек — та же пара, что с точками, и разворот тот же."""
    real = "Иванов Пётр Сергеевич"
    vault = Vault(":memory:", CUSTOMER)
    masked, vault = mask(f"Клиент {real} оформил заказ", vault)
    words = re.findall(r"[А-ЯЁ][а-яё\-]+", masked)
    surname, given, patronymic = words[-3], words[-2], words[-1]
    dotted = f"{surname} {given[0]}.{patronymic[0]}."
    squeezed = f"{surname} {given[0]}{patronymic[0]}"
    back_dotted = redact.unmask_text(
        masked.replace(" ".join(words[-3:]), dotted), vault)
    back_squeezed = redact.unmask_text(
        masked.replace(" ".join(words[-3:]), squeezed), vault)
    check("Иванов" in back_dotted and "П.С." in back_dotted,
          "W4-контроль: пара С ТОЧКАМИ разрешается", back_dotted)
    check("Иванов" in back_squeezed and "ПС" in back_squeezed
          and surname not in back_squeezed,
          "W4: инициалы БЕЗ точек разрешаются тем же разворотом", back_squeezed)
    # НЕГАТИВ: пара, которой в волте нет рядом с ЭТОЙ фамилией, не разворачивается.
    other = redact.unmask_text(
        masked.replace(" ".join(words[-3:]), f"{surname} ЩЩ"), vault)
    check("ЩЩ" in other and "ПС" not in other,
          "W4-негатив: чужая пара не заменяется настоящими инициалами", other)


# ==================================================================== D — W5/W6

def w5_w6_vehicle_ids() -> None:
    """VIN с разделителями и склеенной подсказкой; ПТС со склеенной подсказкой."""
    vault = Vault(":memory:", CUSTOMER)
    masked, vault = mask("номер кузова X96WVZCBZXB6V4218", vault)
    value = masked[len("номер кузова "):]
    grouped = " ".join(value[i:i + 4] for i in range(0, len(value), 4))
    back = redact.unmask_text("номер кузова " + grouped, vault)
    check("X96WVZCBZXB6V4218" in back, "W5: VIN, сгруппированный по четыре", back)
    check("X96WVZCBZXB6V4218" in redact.unmask_text("номеркузова" + value, vault),
          "W5: VIN со склеенной подсказкой")

    vault = Vault(":memory:", CUSTOMER)
    masked, vault = mask("ПТС 78 ЮЩ 778932", vault)
    glued_back = redact.unmask_text("ПТС" + masked[len("ПТС "):], vault)
    # Разделители ЗНАЧЕНИЯ остаются агентские (нотация — его), поэтому сравнение
    # по буквам и цифрам: склейка идёт по ПОДСКАЗКЕ, а не по номеру.
    check(re.sub(r"[^0-9А-ЯЁA-Z]", "", glued_back).endswith("78ЮЩ778932"),
          "W6: ПТС со склеенной подсказкой", glued_back)
    # НЕГАТИВ: 17 символов, не равные подмене, не трогаются.
    check("X96WVZCBZXB6V4219" in redact.unmask_text("X96WVZCBZXB6V4219", vault),
          "W6-негатив: чужой 17-символьный прогон не трогается")


# ====================================================================== E — W7

def _leading_zero(form: str) -> tuple[str, Vault]:
    """Подмена со снятым ведущим нулём у группы — поиск детерминированный."""
    for _ in range(120):
        vault = Vault(":memory:", CUSTOMER)
        masked, vault = mask(form, vault)
        stripped = re.sub(r"(?<![\d])0+(\d)", r"\1", masked)
        if stripped != masked and re.search(r"(?<![\d])0\d", masked):
            return stripped, vault
    return "", Vault(":memory:", CUSTOMER)


def w7_leading_zero() -> None:
    """Ведущий ноль, снятый у группы, возвращает НАСТОЯЩЕЕ значение."""
    for label, real, want in (
            ("PASSPORT", "паспорт 4512 345678", "4512345678"),
            ("SNILS", "СНИЛС 123-456-789 01", "12345678901"),
            ("CARD", "карта 4276 1234 5678 9012", "4276123456789012")):
        stripped, vault = _leading_zero(real)
        back = redact.unmask_text(stripped, vault) if stripped else ""
        got = re.sub(r"\D", "", back)
        check(got == want, f"W7: {label} — ведущий ноль группы снят", f"{stripped!r} -> {back!r}")

    # НЕГАТИВ: ДРУГОЕ число той же формы не разворачивается в это.
    vault = Vault(":memory:", CUSTOMER)
    mask("СНИЛС 123-456-789 01", vault)
    check(re.sub(r"\D", "", redact.unmask_text("СНИЛС 321-456-789 01", vault))
          == "32145678901",
          "W7-негатив: другое число не подменяется настоящим")


# ======================================================= не сломанное ядро (W8)

def _place_core(token: str) -> str:
    """Ядро подмены адреса — улица, дом и настоящий город, без изменяемых частей."""
    core = morph_places.core_phrase(token)
    return core.casefold().replace("ё", "е") or token.casefold()


def _place_part(token: str, role: str) -> str:
    """Значение изменяемой части ПОДМЕНЫ, прочитанное тем же разбором, что у волта."""
    roles = split_roles(token)
    return morph_places.house_digits((roles.get(role) or "").strip())


def core_intact() -> None:
    """Ядро фазы 2 НЕ откатано: значение изменяемой части ключ не двигает.

    Соблазн «пусть квартира форкает подмену» возвращает исходный баг «смена
    квартиры = новый фейк». Поэтому `address_key` (тождество БЕЗ значений) здесь
    пиннится по-прежнему, а равенство ПОЛНЫХ строк заменено на то, что владелец
    назвал в решении: ядро одно, части — разные (W8).
    """
    typed = address_key("улица Лермонтова дом 38 квартира 7")
    check(address_key("улица Лермонтова дом 38 квартира 42") == typed,
          "ядро: смена квартиры не двигает тождество")
    check(address_key("улица Лермонтова дом 39 квартира 7") != typed,
          "ядро: смена дома форкает тождество")
    vault = Vault(":memory:", CUSTOMER)
    full = vault.tokenize("улица Лермонтова дом 38 квартира 7", "LOC")
    other = vault.tokenize("улица Лермонтова дом 38 квартира 42", "LOC")
    check(_place_core(other) == _place_core(full),
          "ядро: смена квартиры — та же улица и тот же дом",
          f"{_place_core(full)!r} / {_place_core(other)!r}")
    check(_place_part(other, "flat") != _place_part(full, "flat"),
          "ядро: смена квартиры — ДРУГАЯ квартира в подмене",
          f"{full!r} / {other!r}")
    check("кв" in full, "ядро: подмена несёт квартиру, а не выбрасывает её", full)
    check(redact.unmask_text(full, vault) == "улица Лермонтова дом 38 квартира 7",
          "ядро: целая подмена размаскировывается")
    check(redact.unmask_text(other, vault) == "улица Лермонтова дом 38 квартира 42",
          "ядро: вторая квартира возвращается ЕЁ настоящей")
    check(canonicalize("LOC", "улица Лермонтова дом 38 кв 7")
          == canonicalize("LOC", "улица Лермонтова дом 38 кв 42"),
          "ядро: канонизация держит маркер и не держит значение")
    check(place_key(full) != place_key("улица Лермонтова дом 39 квартира 7"),
          "ядро: ключ подмены различает дома")


# ============================================ W8 — составной адрес (кластер A)

def w8_compositional_parts() -> None:
    """Ядро одно, части растут на нём — ровно как решил владелец.

    «улица Лермонтова дом 38 квартира 7»  -> «… кв N1»
    «улица Лермонтова дом 38 квартира 42» -> та же улица и дом, «… кв N2»
    «улица Лермонтова дом 38 корпус 1»    -> та же улица и дом, «… корп. N»
    и detokenize каждой строки — её собственная настоящая запись.
    """
    vault = Vault(":memory:", CUSTOMER)
    forms = [
        ("улица Лермонтова дом 38 квартира 7", "flat"),
        ("улица Лермонтова дом 38 квартира 42", "flat"),
        ("улица Лермонтова дом 38 корпус 1", "building"),
        ("улица Лермонтова дом 38 корпус 2", "building"),
        ("улица Лермонтова дом 38 подъезд 3 квартира 7", "entrance"),
        ("улица Лермонтова дом 38 этаж 5 квартира 7", "floor"),
    ]
    tokens = {value: vault.tokenize(value, "LOC") for value, _role in forms}
    cores = {_place_core(token) for token in tokens.values()}
    check(len(cores) == 1,
          "W8: все упоминания одного дома — ОДНО ядро (улица+дом)",
          f"{sorted(cores)}")
    # ЧАСТИ РАЗЛИЧИМЫ ТАМ, ГДЕ РАЗЛИЧАЕТСЯ НАСТОЯЩЕЕ ЗНАЧЕНИЕ.
    for role in ("flat", "building"):
        values = [_place_part(tokens[value], role)
                  for value, part in forms if part == role]
        check(len(set(values)) == len(values),
              f"W8: разные значения части {role!r} — разные подмены",
              f"{values}")
    # …И ОДНО ЗНАЧЕНИЕ — ОДНА ПОДМЕНА, сколько бы раз его ни назвали.
    check(tokens["улица Лермонтова дом 38 квартира 7"]
          == vault.tokenize("улица Лермонтова дом 38 квартира 7", "LOC"),
          "W8: повторное значение части не чеканит второе")
    # ИНСТРУМЕНТ ПОЛУЧАЕТ НАСТОЯЩЕЕ, А НЕ ПОДМЕНУ — на каждой строке.
    for value, _role in forms:
        token = tokens[value]
        check(redact.unmask_text(token, vault) == value,
              f"W8: detokenize возвращает ровно написанное: {value}",
              f"{token!r} -> {redact.unmask_text(token, vault)!r}")
    # ПОПРАВКА «ОЙ НЕ ТА КВАРТИРА» НЕ ЧЕКАНИТ НОВЫЙ ДОМ.
    corrected = vault.tokenize("улица Лермонтова дом 38 квартира 13", "LOC")
    check(_place_core(corrected) == _place_core(tokens[forms[0][0]]),
          "W8: поправка квартиры сохраняет улицу и дом", corrected)
    # НЕГАТИВ: ДРУГОЙ ДОМ — ДРУГОЕ ЯДРО, и подмена части не равна настоящей.
    other_house = vault.tokenize("улица Лермонтова дом 39 квартира 7", "LOC")
    check(_place_core(other_house) != _place_core(tokens[forms[0][0]]),
          "W8-негатив: другой дом — другое ядро", other_house)
    for value, role in forms:
        fake = _place_part(tokens[value], role)
        real = split_roles(value).get(role, "")
        check(fake and fake != morph_places.house_digits(real),
              f"W8-негатив: подмена части {role!r} не равна настоящей",
              f"{fake!r} != {real!r}")
    # ПОЛНЫЙ ПУТЬ МАСКИРОВАНИЯ (не только vault.tokenize): строка, показанная
    # модели, обязана вернуться настоящей — иначе в инструмент уезжает фейк.
    for value, _role in forms:
        masked, leg_vault = mask(value)
        back = redact.unmask_text(masked, leg_vault)
        check(back == value,
              f"W8: полный круг mask/unmask — {value}",
              f"{masked!r} -> {back!r}")
    # ДВА ЧЕЛОВЕКА В ОДНОМ ДОМЕ — ДВЕ РАЗНЫЕ ПОДМЕНЫ (негатив к «слить»).
    couple = Vault(":memory:", CUSTOMER)
    first_flat = couple.tokenize("улица Тверитина, дом 10, квартира 7", "LOC")
    second_flat = couple.tokenize("улица Тверитина, дом 10, квартира 42", "LOC")
    check(first_flat != second_flat
          and _place_core(first_flat) == _place_core(second_flat),
          "W8: два человека в одном доме — один дом, разные квартиры",
          f"{first_flat!r} / {second_flat!r}")


def main() -> int:
    print("phase 4b — пять решений владельца (пин к bench/edge_case_stress.py)")
    for group in (w1_address_leaf, w2_dictated_detok, w3_lowercase_name,
                  w4_squeezed_initials, w5_w6_vehicle_ids, w7_leading_zero,
                  core_intact, w8_compositional_parts):
        print(f"\n{group.__name__}")
        group()
    failed = [name for ok, name, _ in RESULTS if not ok]
    print(f"\n{'=' * 70}")
    print(f"ИТОГО: {len(RESULTS) - len(failed)}/{len(RESULTS)} проверок пройдено")
    for name in failed:
        print(f"  ПРОВАЛ: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
