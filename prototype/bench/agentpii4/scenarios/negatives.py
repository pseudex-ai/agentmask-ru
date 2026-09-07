"""Значения, которые ОБЯЗАНЫ уцелеть: вторая половина прибора.

ПОЛНОТУ БЕЗ ТОЧНОСТИ ПОКУПАЕТ ОДНА СТРОКА «МАСКИРОВАТЬ ВСЁ». v4 мерил только
полноту: `Case.negatives` объявлен, API написан (`common.MessageDraft.negative`),
и ни одна семья его ни разу не вызвала — значит самый частый способ сломать
агента, замаскировать не-ПД, не мерился ничем, и все числа описывали половину
прибора.

СЕМЬИ ВЗЯТЫ ИЗ v3, А НЕ ПРИДУМАНЫ ЗАНОВО: они выведены из корпуса реальной
диспетчерской речи, где «число рядом с кабинетом» встречается 528 раз, а «улица»
без имени — 73. Формулировок у каждой четыре, а не одна: шестьдесят копий одного
предложения меряют одну строку много раз и печатают счёт как покрытие.

ДВА ПРАВИЛА, БЕЗ КОТОРЫХ НЕГАТИВ ПЕРЕСТАЁТ БЫТЬ НЕГАТИВОМ:

  * РЯДОМ С АДРЕСОМ МОЖНО НЕ ВСЁ. Голый «шестой подъезд» возле настоящей улицы
    — это ЧАСТЬ адреса, и требовать, чтобы он уцелел, значит требовать от
    движка ошибки. Такие семьи отданы случаям, где места нет вовсе.
  * `voice_itn` ОПРЕДЕЛЁН тем, что обратная нормализация включена, поэтому
    случай в нём обязан нести цифру; негатив без числа оставил бы его без
    единой, то есть превратил бы в `voice_raw` под чужим именем.
"""
import random

from bench.agentpii4 import pools

# Единицы счёта и измерения. Первые не делают число номером дома, вторые —
# ровно тот класс, из-за которого «территория завода пять гектаров» проходила
# все адресные признаки.
_QUANTITY: tuple[str, ...] = ("коробки", "штуки", "места", "паллеты", "филиала", "пакета")
_MEASURE: tuple[str, ...] = ("гектаров", "километров", "метров", "тонн", "литров")

# Города как МЕСТО, а не как чей-то адрес: под 152-ФЗ ст. 3 п. 1 город никого
# не определяет, и мы отказываемся его маскировать намеренно.
_CITY_REFS: tuple[str, ...] = ("москве", "казани", "перми", "туле", "омске", "твери")

_WITH_ADDRESS: tuple[str, ...] = ("order_number", "room_number", "time_of_day",
                                  "quantity", "measure", "fare")
_WITHOUT_ADDRESS: tuple[str, ...] = _WITH_ADDRESS + (
    "city_reference", "street_no_name", "flat_as_home", "entrance_no_street")
_WITH_DIGITS: frozenset[str] = frozenset({
    "order_number", "room_number", "time_of_day", "quantity", "measure"})


def kinds_for(register: str, beside_address: bool) -> tuple[str, ...]:
    kinds = _WITH_ADDRESS if beside_address else _WITHOUT_ADDRESS
    if register != "voice_itn":
        return kinds
    return tuple(kind for kind in kinds if kind in _WITH_DIGITS)


def draw(register: str, rng: random.Random, beside_address: bool,
         ) -> tuple[str, str, str, str, str]:
    """(слова до, значение, слова после, семья, почему) — одна реплика."""
    kind = rng.choice(kinds_for(register, beside_address))
    return _chunk(kind, register, rng)


def _number(value: int, register: str) -> str:
    return pools.spell_cardinal(value) if register == "voice_raw" else str(value)


def _chunk(kind: str, register: str, rng: random.Random,
           ) -> tuple[str, str, str, str, str]:
    if kind == "order_number":
        return ("заказ", _number(rng.randint(101, 899), register), "", kind,
                "номер заказа — не персональные данные; продиктованный вслух он "
                "маскировался целиком, и это уже отгружалось")
    if kind == "room_number":
        room = rng.randint(2, 12)
        place = rng.choice(("кабинет", "отделение"))
        value = (f"{pools.spell_ordinal(room)} {place}" if register == "voice_raw"
                 else f"{room} {place}")
        return ("", value, "", kind,
                "число рядом с кабинетом или отделением — крупнейший источник "
                "ложных срабатываний речевого регистра")
    if kind == "time_of_day":
        hour = rng.choice((8, 9, 10, 11, 12))
        if register == "voice_raw":
            spoken = {8: "восьми", 9: "девяти", 10: "десяти",
                      11: "одиннадцати", 12: "двенадцати"}[hour]
            return ("к", f"{spoken} ноль ноль", "", kind,
                    "время; ноли проговариваются словом и дают тот же пробег "
                    "числительных, что и номер")
        # Без двоеточия: два регистра из пяти определены тем, что не несут
        # предложенческой пунктуации вовсе.
        return ("к", f"{hour} часам", "", kind, "время, а не номер")
    if kind == "quantity":
        count = rng.randint(2, 12)
        return ("", f"{_number(count, register)} {rng.choice(_QUANTITY)}", "", kind,
                "числительное с единицей счёта — не номер дома")
    if kind == "measure":
        count = rng.randint(2, 40)
        return ("", f"{_number(count, register)} {rng.choice(_MEASURE)}", "", kind,
                "число с единицей измерения: «территория пять гектаров» проходит "
                "все адресные признаки и адресом не является")
    if kind == "city_reference":
        city = rng.choice(_CITY_REFS)
        return ("такое бывает в", city.capitalize() if register == "clean" else city,
                "", kind,
                "город как место, а не как чей-то адрес; под 152-ФЗ ст. 3 п. 1 "
                "он никого не определяет")
    if kind == "street_no_name":
        before, value, after = rng.choice((
            ("на", "улице", "холодно"), ("на", "улице", "дождь"),
            ("по", "улицам", "не пройти"), ("выйду на", "улицу", "подожду")))
        return (before, value, after, kind,
                "«улица» без имени — двор, погода, прогулка")
    if kind == "flat_as_home":
        before, value, after = rng.choice((
            ("", "квартиру", "снимаю"), ("", "квартиру", "убираю"),
            ("в", "квартире", "холодно"), ("", "квартиру", "недавно купили")))
        return (before, value, after, kind,
                "«квартира» без номера — жильё, а не адрес")
    if kind == "entrance_no_street":
        number = rng.randint(2, 8)
        value = (f"{pools.spell_ordinal(number)} подъезд" if register == "voice_raw"
                 else f"подъезд {number}")
        return ("", value, "", kind,
                "адресный хвост без адреса: улицы в реплике нет")
    if kind == "fare":
        before, value, after = rng.choice((
            ("", "проезд", "пятьдесят рублей"), ("", "проезд", "подорожал"),
            ("", "проезд", "оплатил картой"), ("за", "проезд", "наличными")))
        return (before, value, after, kind, "«проезд» как плата, а не как тип улицы")
    raise ValueError(f"неизвестная семья негатива {kind!r}")


def main() -> int:
    failures = 0
    for register in ("clean", "chat", "sloppy", "voice_itn", "voice_raw"):
        for beside in (True, False):
            for seed in range(60):
                rng = random.Random(f"neg:{register}:{beside}:{seed}")
                before, value, after, family, why = draw(register, rng, beside)
                if not value or not family or not why:
                    failures += 1
                    print("FAIL пустое поле", register, beside, seed)
                if register == "voice_itn" and not any(ch.isdigit() for ch in value):
                    failures += 1
                    print(f"FAIL voice_itn без цифры: {value!r}")
                if beside and family in ("city_reference", "street_no_name",
                                         "flat_as_home", "entrance_no_street"):
                    failures += 1
                    print(f"FAIL {family} рядом с адресом")
                if any(ch in value for ch in '"\\'):
                    failures += 1
                    print(f"FAIL кавычка в значении: {value!r}")
    print("negatives: PASS" if not failures else f"negatives: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
