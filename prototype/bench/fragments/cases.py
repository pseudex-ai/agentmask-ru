"""Корпус случаев: что заказчик написал, что агент переписал, и что обязано вернуться.

ДВЕ СТОРОНЫ В ОДНОМ КОРПУСЕ, И НИ ОДНА НЕ ГЛАВНЕЕ.

  НАШЕ (`SIDE_OURS`)     — мы отчеканили подмену, агент написал её в какой-то
                           форме; настоящее значение обязано вернуться. Не
                           вернулось — фейк доехал до инструмента заказчика.
  ЧУЖОЕ (`SIDE_FOREIGN`) — число, которого мы НИКОГДА не подменяли (количество,
                           сумма, артикул, номер склада, дата документа);
                           обязано вернуться байт в байт. Вернулось другим — это
                           порча данных в CRM заказчика, и она всегда молчит.

ФОРМЫ АГЕНТА НЕ ВЫДУМАНЫ. Мы точно знаем, что пишет модель: дословную подмену,
телефон через 8 и голыми цифрами, последние четыре цифры, адрес РАЗЛОЖЕННЫЙ ПО
ПОЛЯМ СХЕМЫ, улицу без дома, дом без улицы, дату в чужой нотации и ISO, паспорт
двумя полями, имя склонённое, транслитом и инициалами. Предшественники слали
подмену ДОСЛОВНО и слали `street` и `house` ПОРОЗНЬ — и поэтому показывали ноль
там, где потерь было двенадцать из двенадцати.

ЧУЖИЕ ЧИСЛА НЕ СЛУЧАЙНЫ. `forge_foreign` берёт цифры ИЗ СЕРЕДИНЫ уже
отчеканенных подмен: столкновение обязано быть неизбежным, иначе прибор меряет
удачу и на пустом волте показывает зелено. Рядом — числа, заведомо не лежащие ни
в одной подмене; если такое не нашлось, это ошибка, а не повод взять любое.

СКЛОНЯЕТ ИМЯ САМ ДВИЖОК, А НЕ ПРИБОР. Дательный падеж подмены берётся чеканкой
второго носителя («Позвоните Иванову Петру»), а не морфологией, написанной
здесь: своя морфология ошибалась бы, и её ошибки легли бы в числа как поломки
движка. Транслит — наоборот, дело АГЕНТА, поэтому таблица здесь своя.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from bench.fragments.engine import Minted, Seed
from bench.fragments.surfaces import SIDE_FOREIGN, SIDE_OURS, Passage

# --- настоящие значения заказчика -------------------------------------------
# У КАЖДОГО СЛУЧАЯ СВОЙ ЧЕЛОВЕК, и это не украшение, а поправка на свойство
# движка, найденная этим же прибором. Подмена чеканится в ПЕРВОМ разговоре, где
# значение встретилось, и узнавание КУСКА подмены разрешено только там
# (`Vault.minted_in`). Один человек на весь корпус означал бы, что тридцать два
# случая из тридцати трёх спрашивают о куске в чужом разговоре, и столбец
# «разговор назван» провалился бы целиком — артефакт прибора, а не дефект.
#
# Контрольные суммы СНИЛС/ИНН/карты посчитаны один раз и приколочены литералами:
# считать их здесь заново значило бы повторить арифметику движка и сверять его с
# ним же. Если движок перестанет их видеть, `Engine.mint` поднимет `MintFailed`,
# а не зачтёт случай молча.

_SNILS_POOL = (
    "705-622-259 76", "305-701-084 27", "049-762-875 16", "805-596-192 27",
    "018-609-257 58", "356-819-182 17", "349-745-737 36", "783-794-906 82",
    "581-168-414 00", "514-762-287 89",
)
_INN_POOL = (
    "6929312905", "2020381037", "0788494039", "8387614953", "0051326473",
    "8279840850", "0408698818", "6292836270", "3275212541", "4366357257",
)
_CARD_POOL = (
    "4582 0615 1537 1169", "4034 4171 7009 8204", "4822 0763 1728 5318",
    "4607 3361 6869 0730", "4079 9435 6322 8450", "4800 9408 5563 3591",
    "4557 1370 0961 8165", "4222 7771 8237 3149", "4157 8704 6438 5870",
    "4080 1020 5297 5256",
)
# Дательный падеж написан здесь руками и парой к именительному: склонять имя
# прибором значило бы писать свою морфологию, а её ошибки легли бы в числа как
# поломки движка. Подмену в дательном чеканит сам движок — вторым носителем.
_NAMES = (
    ("Иванов Пётр Сергеевич", "Иванову Петру"),
    ("Кузнецов Дмитрий Олегович", "Кузнецову Дмитрию"),
    ("Соколов Андрей Викторович", "Соколову Андрею"),
    ("Морозов Сергей Павлович", "Морозову Сергею"),
    ("Волков Никита Алексеевич", "Волкову Никите"),
    ("Зайцев Роман Юрьевич", "Зайцеву Роману"),
)
# Улицы случаев и улицы фона не пересекаются: пересечение сделало бы
# «столкнулось с чужой подменой» и «это та же улица» неразличимыми в дампе.
_CASE_STREETS = ("Абрикосовая", "Берёзовая", "Виноградная", "Гвоздичная",
                 "Дубравная", "Ежевичная", "Жасминовая", "Земляничная")


@dataclass(frozen=True)
class Person:
    """Заказчикова запись об одном человеке — то, что он написал в диалоге."""

    phone: str
    address: str
    date: str
    passport: str
    name: str
    name_dative: str
    snils: str
    inn: str
    card: str


def person(index: int) -> Person:
    nominative, dative = _NAMES[index % len(_NAMES)]
    return Person(
        phone=(f"+7 9{50 + index % 40:02d} {200 + index:03d}-"
               f"{10 + index % 80:02d}-{11 + index % 70:02d}"),
        address=(f"улица {_CASE_STREETS[index % len(_CASE_STREETS)]}, "
                 f"{3 + index % 90}, кв. {2 + index % 60}"),
        date=f"{1 + index % 27:02d}.{1 + index % 12:02d}.19{70 + index % 25}",
        passport=f"45{10 + index % 80:02d} {100000 + index * 37:06d}",
        name=nominative,
        name_dative=dative,
        snils=_SNILS_POOL[index % len(_SNILS_POOL)],
        inn=_INN_POOL[index % len(_INN_POOL)],
        card=_CARD_POOL[index % len(_CARD_POOL)],
    )


# Подводка — единственное, что обязано пережить маскирование дословно: по ней
# `Engine.mint` вырезает подмену. Она же даёт движку контекст, без которого он
# не увидит ни дату рождения, ни паспорт.
_CUES = {
    "phone": "Телефон клиента: ",
    "address": "Адрес доставки: ",
    "date": "Дата рождения: ",
    "passport": "Паспорт: ",
    "snils": "СНИЛС: ",
    "inn": "ИНН: ",
    "card": "Номер карты: ",
    "name": "Клиент: ",
    "name_dative": "Позвоните ",
}


def _seed(role: str, who: Person) -> Seed:
    value = {
        "phone": who.phone, "address": who.address, "date": who.date,
        "passport": who.passport, "snils": who.snils, "inn": who.inn,
        "card": who.card, "name": who.name, "name_dative": who.name_dative,
    }[role]
    return Seed(role=role, cue=_CUES[role], value=value)


MONTHS = ("января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря")

# Транслитерация — привычка АГЕНТА, не движка, поэтому таблица своя и простая.
# Широкая, а не точная: принимаются несколько написаний одного имени, потому что
# узкая таблица объявила бы поломкой чужую, но законную конвенцию — урок v4.
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

# Буквы, у которых нет ОДНОГО правильного написания: три стандарта плюс
# «общепринятое» расходятся ровно здесь, и модель выбирает любое из них.
AMBIGUOUS = {
    "е": ("e", "ye"), "ё": ("e", "yo", "ye"), "й": ("y", "i", ""),
    "ю": ("yu", "iu", "ju"), "я": ("ya", "ia", "ja"), "ы": ("y", "i"),
    "х": ("kh", "h"), "ц": ("ts", "c"), "щ": ("shch", "sch"), "ж": ("zh", "j"),
}


def digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def transliterate(word: str) -> str:
    out = "".join(TRANSLIT.get(letter.lower(), letter) for letter in word)
    return out[:1].upper() + out[1:]


def transliterate_variants(word: str) -> tuple[str, ...]:
    """Все написания, которые считаются тем же именем.

    ШИРОКО ПО СЛОГУ, И НИКОГДА ПО РАССТОЯНИЮ. Прибор со своей единственной
    таблицей объявил бы поломкой «Sergei» там, где движок вернул совершенно
    верное имя (измерено этим же прибором в первом прогоне) — ровно ошибка,
    которую v4 стоила 1.4 процентных пункта на оси значений. Расстояние Левенштейна
    вместо перечисления недопустимо: чужое имя тоже стоит в одной правке.
    """
    seeds: list[str] = [""]
    for letter in word:
        renderings = AMBIGUOUS.get(letter.lower(), (TRANSLIT.get(letter.lower(), letter),))
        seeds = [head + tail for head in seeds for tail in renderings]
        if len(seeds) > 256:
            raise ValueError(f"слишком много написаний для {word!r} — перечисление вышло из берегов")
    return tuple(one[:1].upper() + one[1:] for one in seeds)


def transliterate_name(parts: Sequence[str]) -> tuple[str, ...]:
    """Имя целиком во всех принятых написаниях — декартово произведение по словам."""
    joined: list[str] = [""]
    for index, part in enumerate(parts):
        variants = transliterate_variants(part)
        joined = [(head + (" " if index else "") + one) for head in joined for one in variants]
        if len(joined) > 1024:
            raise ValueError(f"слишком много написаний для {parts!r}")
    return tuple(joined)


@dataclass(frozen=True)
class AddressParts:
    street: str
    house: str
    flat: str


def split_address(value: str) -> AddressParts:
    """Разобрать адрес на улицу, дом и квартиру — разбором ПРИБОРА, не движка.

    Импортировать `morph_places.split_roles` было бы удобно и неверно: прибор
    спрашивал бы у подсудимого, где у его подмены дом, и совпал бы с ним по
    построению. Формат подмены фиксирован чеканкой; если он изменится, здесь
    будет явная ошибка, а не тихо другое поле.
    """
    match = re.fullmatch(r"(?P<street>[^,]+),\s*(?P<house>[^,]+),\s*кв\.\s*(?P<flat>\S+)",
                         value.strip())
    if match is None:
        raise ValueError(f"адрес {value!r} не разбирается на улицу, дом и квартиру")
    return AddressParts(street=match.group("street").strip(),
                        house=match.group("house").strip(),
                        flat=match.group("flat").strip())


def date_in_words(dotted: str) -> str:
    day, month, year = dotted.split(".")
    return f"{int(day)} {MONTHS[int(month) - 1]} {year}"


def date_iso(dotted: str) -> str:
    day, month, year = dotted.split(".")
    return f"{year}-{month}-{day}"


def date_slashed(dotted: str) -> str:
    day, month, year = dotted.split(".")
    return f"{day}/{month}/{year[2:]}"


@dataclass(frozen=True)
class Piece:
    """Один кусок вызова: что написал агент и что обязано вернуться на его месте."""

    side: str
    label: str
    field: str
    anchor: str
    written: str
    accepted: tuple[str, ...]


@dataclass(frozen=True)
class Written:
    passage: Passage
    pieces: tuple[Piece, ...]


def compose(tool_name: str, pieces: Sequence[Piece]) -> Written:
    """Собрать оба представления из ОДНИХ И ТЕХ ЖЕ кусков.

    Одна сборка на весь корпус: если бы каждый случай писал прозу сам, аргумент
    и проза разошлись бы по содержанию и разница поверхностей читалась бы как
    разница текстов.
    """
    prose = "; ".join(f"{piece.anchor} {piece.written}" for piece in pieces)
    return Written(
        passage=Passage(
            tool_name=tool_name,
            fields=tuple((piece.field, piece.written) for piece in pieces),
            prose=prose,
        ),
        pieces=tuple(pieces),
    )


@dataclass(frozen=True)
class Foreign:
    """Собственные числа заказчика для одной клетки.

    `colliding_*` построены так, что столкновение с цифрами выданных подмен
    неизбежно; `clean_*` — так, что его нет ни с одной. `sources` называет, из
    какой подмены взяты цифры, чтобы лист провала читался без догадок.
    """

    colliding_quantity: str
    colliding_amount: str
    colliding_article: str
    clean_quantity: str
    clean_amount: str
    clean_article: str
    sources: tuple[str, ...]


def _rotate(fakes: Sequence[str], step: int) -> tuple[str, ...]:
    """Начать перебор с другой подмены, чтобы три числа пришли из трёх разных.

    Три числа из одной подмены мерили бы одну и ту же строку волта три раза и
    выдавали бы это за три независимых наблюдения.
    """
    if not fakes:
        return ()
    cut = step % len(fakes)
    return tuple(fakes[cut:]) + tuple(fakes[:cut])


def _lift(fakes: Sequence[str], length: int) -> tuple[str, str]:
    """Вырезать цифры ИЗ СЕРЕДИНЫ подмены: столкновение по построению, не по удаче.

    Строго из середины (не префикс и не суффикс) — иначе это было бы «начало
    фейкового телефона», то есть кусок с краем, а край сам по себе подсказка;
    дефект же ловится ровно на куске, который о себе не говорит ничего.
    """
    for fake in fakes:
        body = digits(fake)
        for start in range(2, len(body) - length):
            lifted = body[start:start + length]
            if lifted[0] != "0":
                return lifted, fake
    raise ValueError(
        f"в фоне нет подмены, из СЕРЕДИНЫ которой режется {length} цифр — "
        f"столкновение не построить, а брать наугад нельзя")


def _clean(fakes: Sequence[str], length: int) -> str:
    """Число той же длины, которого нет ни внутри одной подмены."""
    bodies = tuple(digits(fake) for fake in fakes)
    low, high = 10 ** (length - 1), 10 ** length
    for candidate in range(low, high):
        text = str(candidate)
        if not any(text in body for body in bodies):
            return text
    raise ValueError(
        f"все {length}-значные числа лежат внутри подмен — «чистую» половину "
        f"корпуса не построить, и молча подставить любое нельзя")


def forge_foreign(background: Sequence[str]) -> Foreign:
    quantity, from_quantity = _lift(_rotate(background, 0), 3)
    amount, from_amount = _lift(_rotate(background, 1), 4)
    article, from_article = _lift(_rotate(background, 2), 6)
    clean_quantity = _clean(background, 3)
    clean_amount = _clean(background, 4)
    clean_article = _clean(background, 6)
    return Foreign(
        colliding_quantity=quantity,
        colliding_amount=amount,
        colliding_article=article,
        clean_quantity=clean_quantity,
        clean_amount=clean_amount,
        clean_article=clean_article,
        sources=(f"{quantity} ⊂ {from_quantity}",
                 f"{amount} ⊂ {from_amount}",
                 f"{article} ⊂ {from_article}"),
    )


Writer = Callable[[Mapping[str, Minted], Foreign], Written]


@dataclass(frozen=True)
class Case:
    case_id: str
    family: str
    form: str
    seeds: tuple[Seed, ...]
    write: Writer


def ours(label: str, field: str, anchor: str, written: str,
         accepted: Sequence[str]) -> Piece:
    return Piece(side=SIDE_OURS, label=label, field=field, anchor=anchor,
                 written=written, accepted=tuple(accepted))


def foreign(label: str, field: str, anchor: str, written: str) -> Piece:
    """Чужое обязано вернуться БАЙТ В БАЙТ — принимается ровно написанное."""
    return Piece(side=SIDE_FOREIGN, label=label, field=field, anchor=anchor,
                 written=written, accepted=(written,))


# --- формы телефона ---------------------------------------------------------

def _phone_full(real: str) -> tuple[str, ...]:
    body = digits(real)
    return (real, body, "8" + body[1:], body[-10:])


def _phone_verbatim(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["phone"]
    return compose("crm.create_order", [
        ours("телефон дословно", "phone", "телефон", pair.fake, _phone_full(pair.real))])


def _phone_through_8(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["phone"]
    written = "8" + digits(pair.fake)[1:]
    return compose("crm.create_order", [
        ours("телефон через 8", "phone", "телефон", written, _phone_full(pair.real))])


def _phone_bare(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["phone"]
    return compose("crm.create_order", [
        ours("телефон голыми цифрами", "phone", "телефон", digits(pair.fake),
             _phone_full(pair.real))])


def _phone_last4(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["phone"]
    return compose("crm.verify_caller", [
        ours("последние 4 цифры телефона", "last_digits", "последние цифры",
             digits(pair.fake)[-4:], (digits(pair.real)[-4:],))])


# --- формы адреса -----------------------------------------------------------

def _street_forms(street: str) -> tuple[str, ...]:
    bare = street.split(" ", 1)[1] if " " in street else street
    return (street, bare, f"ул. {bare}")


def _addr_whole(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["address"]
    return compose("crm.create_order", [
        ours("адрес целиком", "address", "адрес доставки", pair.fake, (pair.real,))])


def _addr_fields(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["address"]
    fake, real = split_address(pair.fake), split_address(pair.real)
    return compose("crm.create_order", [
        ours("улица в своём поле", "street", "улица", fake.street,
             _street_forms(real.street)),
        ours("дом в своём поле", "house", "дом", fake.house, (real.house,)),
        ours("квартира в своём поле", "flat", "квартира", fake.flat, (real.flat,)),
    ])


def _addr_street_only(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["address"]
    fake, real = split_address(pair.fake), split_address(pair.real)
    return compose("crm.find_route", [
        ours("улица без дома", "street", "улица", fake.street,
             _street_forms(real.street))])


def _addr_house_only(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["address"]
    fake, real = split_address(pair.fake), split_address(pair.real)
    return compose("crm.find_route", [
        ours("дом без улицы", "house", "дом", fake.house, (real.house,))])


# --- формы даты -------------------------------------------------------------

def _date_verbatim(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["date"]
    return compose("crm.create_client", [
        ours("дата дословно", "birth_date", "дата рождения", pair.fake,
             (pair.real, pair.real.lstrip("0")))])


def _date_slashed(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["date"]
    real = date_slashed(pair.real)
    return compose("crm.create_client", [
        ours("дата в другой нотации", "birth_date", "дата рождения",
             date_slashed(pair.fake), (real, real.lstrip("0")))])


def _date_iso(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["date"]
    return compose("crm.create_client", [
        ours("дата в ISO", "birth_date", "дата рождения", date_iso(pair.fake),
             (date_iso(pair.real),))])


def _date_words(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["date"]
    real = date_in_words(pair.real)
    return compose("crm.create_client", [
        ours("дата словами", "birth_date", "дата рождения", date_in_words(pair.fake),
             (real, f"{real} года", pair.real))])


# --- документы --------------------------------------------------------------

def _passport_whole(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["passport"]
    return compose("crm.attach_document", [
        ours("паспорт целиком", "passport", "паспорт", pair.fake,
             (pair.real, digits(pair.real)))])


def _passport_two_fields(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["passport"]
    fake, real = digits(pair.fake), digits(pair.real)
    return compose("crm.attach_document", [
        ours("серия паспорта", "passport_series", "серия паспорта", fake[:4],
             (real[:4],)),
        ours("номер паспорта", "passport_number", "номер паспорта", fake[4:],
             (real[4:],)),
    ])


def _snils_verbatim(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["snils"]
    return compose("crm.attach_document", [
        ours("СНИЛС дословно", "snils", "СНИЛС", pair.fake,
             (pair.real, digits(pair.real)))])


def _snils_bare(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["snils"]
    return compose("crm.attach_document", [
        ours("СНИЛС голыми цифрами", "snils", "СНИЛС", digits(pair.fake),
             (digits(pair.real), pair.real))])


def _inn_verbatim(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["inn"]
    return compose("crm.attach_document", [
        ours("ИНН дословно", "inn", "ИНН", pair.fake, (pair.real,))])


def _card_verbatim(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["card"]
    return compose("billing.charge", [
        ours("карта дословно", "card", "карта", pair.fake,
             (pair.real, digits(pair.real)))])


def _card_last4(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["card"]
    return compose("billing.charge", [
        ours("последние 4 цифры карты", "card_last4", "последние цифры карты",
             digits(pair.fake)[-4:], (digits(pair.real)[-4:],))])


# --- формы имени ------------------------------------------------------------

def _name_verbatim(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["name"]
    return compose("crm.create_client", [
        ours("имя дословно", "name", "клиент", pair.fake, (pair.real,))])


def _name_declined(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["name_dative"]
    nominative = minted["name"]
    return compose("crm.create_task", [
        ours("имя склонённое", "assignee", "поручить", pair.fake,
             (pair.real, nominative.real))])


def _name_translit(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["name"]
    fake = pair.fake.split()
    real = pair.real.split()
    written = f"{transliterate(fake[0])} {transliterate(fake[1])}"
    return compose("crm.create_client", [
        ours("имя транслитом", "name", "клиент", written,
             transliterate_name(real[:2]) + (f"{real[0]} {real[1]}", pair.real))])


def _name_initials(minted: Mapping[str, Minted], _foreign: Foreign) -> Written:
    pair = minted["name"]
    fake = pair.fake.split()
    real = pair.real.split()
    return compose("crm.create_client", [
        ours("имя инициалами", "name", "клиент",
             f"{fake[0]} {fake[1][0]}. {fake[2][0]}.",
             (f"{real[0]} {real[1][0]}. {real[2][0]}.",
              f"{real[0]} {real[1][0]}.{real[2][0]}.", pair.real))])


# --- собственные числа заказчика --------------------------------------------

def _foreign_quantity(_minted: Mapping[str, Minted], numbers: Foreign) -> Written:
    return compose("crm.add_line", [
        foreign("количество, столкнувшееся с подменой", "quantity", "количество",
                numbers.colliding_quantity)])


def _foreign_amount(_minted: Mapping[str, Minted], numbers: Foreign) -> Written:
    return compose("billing.invoice", [
        foreign("сумма, столкнувшаяся с подменой", "amount", "сумма",
                numbers.colliding_amount)])


def _foreign_article(_minted: Mapping[str, Minted], numbers: Foreign) -> Written:
    return compose("crm.add_line", [
        foreign("артикул, столкнувшийся с подменой", "article", "артикул",
                numbers.colliding_article)])


def _foreign_clean(_minted: Mapping[str, Minted], numbers: Foreign) -> Written:
    return compose("crm.add_line", [
        foreign("количество без столкновения", "quantity", "количество",
                numbers.clean_quantity),
        foreign("сумма без столкновения", "amount", "сумма", numbers.clean_amount),
        foreign("артикул без столкновения", "article", "артикул",
                numbers.clean_article),
    ])


def _foreign_warehouse(_minted: Mapping[str, Minted], _numbers: Foreign) -> Written:
    return compose("crm.set_warehouse", [
        foreign("адрес склада заказчика", "address", "склад",
                "улица Магистральная, 7, кв. 3"),
        foreign("улица склада", "street", "улица склада", "улица Магистральная"),
        foreign("номер склада", "house", "дом склада", "7"),
    ])


def _foreign_documents(_minted: Mapping[str, Minted], _numbers: Foreign) -> Written:
    return compose("crm.attach_invoice", [
        foreign("номер счёта", "invoice", "счёт", "СЧ-2025-004417"),
        foreign("трек-номер", "track", "трек", "RU123456789CN"),
        foreign("дата документа", "document_date", "дата счёта", "05.05.2026"),
    ])


# --- смешанные вызовы: наше и чужое в одном листе ---------------------------

def _mixed_address_and_quantity(minted: Mapping[str, Minted],
                                numbers: Foreign) -> Written:
    pair = minted["address"]
    fake, real = split_address(pair.fake), split_address(pair.real)
    return compose("crm.create_order", [
        ours("улица в своём поле", "street", "улица", fake.street,
             _street_forms(real.street)),
        ours("дом в своём поле", "house", "дом", fake.house, (real.house,)),
        foreign("количество, столкнувшееся с подменой", "quantity", "количество",
                numbers.colliding_quantity),
    ])


def _mixed_phone_and_amount(minted: Mapping[str, Minted], numbers: Foreign) -> Written:
    pair = minted["phone"]
    return compose("crm.create_order", [
        ours("телефон дословно", "phone", "телефон", pair.fake, _phone_full(pair.real)),
        foreign("сумма, столкнувшаяся с подменой", "amount", "сумма",
                numbers.colliding_amount),
    ])


def _mixed_phone_and_own_collision(minted: Mapping[str, Minted],
                                   _numbers: Foreign) -> Written:
    """Число заказчика, столкнувшееся с подменой ИЗ ЭТОГО ЖЕ разговора.

    Область разговора здесь не помогает по построению: цифры лежат внутри нашей
    собственной подмены этого диалога. Это та конфигурация, которую отклонённая
    правка объявляла лекарством, — и в которой дефект, по записи Б29, жив.
    """
    pair = minted["phone"]
    return compose("crm.create_order", [
        ours("телефон дословно", "phone", "телефон", pair.fake, _phone_full(pair.real)),
        foreign("количество из цифр нашей же подмены", "quantity", "количество",
                digits(pair.fake)[4:7]),
    ])


def _mixed_name_and_order(minted: Mapping[str, Minted], numbers: Foreign) -> Written:
    pair = minted["name"]
    return compose("crm.create_task", [
        ours("имя дословно", "name", "клиент", pair.fake, (pair.real,)),
        foreign("номер заказа без столкновения", "order", "заказ",
                numbers.clean_article),
    ])


@dataclass(frozen=True)
class Spec:
    """Случай без людей: роли, которые ему нужны, и как агент их переписал."""

    case_id: str
    family: str
    form: str
    roles: tuple[str, ...]
    write: Writer


_SPECS: tuple[Spec, ...] = (
    Spec("phone_verbatim", "phone", "дословно", ("phone",), _phone_verbatim),
    Spec("phone_through_8", "phone", "через 8", ("phone",), _phone_through_8),
    Spec("phone_bare_digits", "phone", "голые цифры", ("phone",), _phone_bare),
    Spec("phone_last4", "phone", "последние 4", ("phone",), _phone_last4),
    Spec("addr_whole", "address", "целиком", ("address",), _addr_whole),
    Spec("addr_fields", "address", "по полям схемы", ("address",), _addr_fields),
    Spec("addr_street_only", "address", "улица без дома", ("address",),
         _addr_street_only),
    Spec("addr_house_only", "address", "дом без улицы", ("address",),
         _addr_house_only),
    Spec("date_verbatim", "date", "дословно", ("date",), _date_verbatim),
    Spec("date_slashed", "date", "другая нотация", ("date",), _date_slashed),
    Spec("date_iso", "date", "ISO", ("date",), _date_iso),
    Spec("date_words", "date", "словами", ("date",), _date_words),
    Spec("passport_whole", "passport", "целиком", ("passport",), _passport_whole),
    Spec("passport_two_fields", "passport", "двумя полями", ("passport",),
         _passport_two_fields),
    Spec("snils_verbatim", "snils", "дословно", ("snils",), _snils_verbatim),
    Spec("snils_bare_digits", "snils", "голые цифры", ("snils",), _snils_bare),
    Spec("inn_verbatim", "inn", "дословно", ("inn",), _inn_verbatim),
    Spec("card_verbatim", "card", "дословно", ("card",), _card_verbatim),
    Spec("card_last4", "card", "последние 4", ("card",), _card_last4),
    Spec("name_verbatim", "name", "дословно", ("name",), _name_verbatim),
    Spec("name_declined", "name", "склонённое", ("name", "name_dative"),
         _name_declined),
    Spec("name_translit", "name", "транслит", ("name",), _name_translit),
    Spec("name_initials", "name", "инициалы", ("name",), _name_initials),
    Spec("foreign_quantity", "foreign", "количество \u2282 подмена", (), _foreign_quantity),
    Spec("foreign_amount", "foreign", "сумма \u2282 подмена", (), _foreign_amount),
    Spec("foreign_article", "foreign", "артикул \u2282 подмена", (), _foreign_article),
    Spec("foreign_clean", "foreign", "без столкновения", (), _foreign_clean),
    Spec("foreign_warehouse", "foreign", "адрес склада", (), _foreign_warehouse),
    Spec("foreign_documents", "foreign", "счёт, трек, дата", (), _foreign_documents),
    Spec("mixed_address_and_quantity", "mixed", "адрес по полям + количество",
         ("address",), _mixed_address_and_quantity),
    Spec("mixed_phone_and_amount", "mixed", "телефон + сумма", ("phone",),
         _mixed_phone_and_amount),
    Spec("mixed_phone_and_own_collision", "mixed", "телефон + своё же число",
         ("phone",), _mixed_phone_and_own_collision),
    Spec("mixed_name_and_order", "mixed", "имя + номер заказа", ("name",),
         _mixed_name_and_order),
)


def _build(index: int, spec: Spec) -> Case:
    who = person(index)
    return Case(case_id=spec.case_id, family=spec.family, form=spec.form,
                seeds=tuple(_seed(role, who) for role in spec.roles),
                write=spec.write)


CORPUS: tuple[Case, ...] = tuple(
    _build(index, spec) for index, spec in enumerate(_SPECS))


# --- фон: чем наполняется волт ----------------------------------------------

_BACKGROUND_STREETS = ("Полевая", "Тополиная", "Садовая", "Лесная", "Школьная",
                       "Речная", "Луговая", "Зелёная", "Северная", "Южная")
_BACKGROUND_NAMES = ("Гагарин Пётр Ильич", "Иванова Мария Львовна",
                     "Сомов Игорь Львович", "Петрова Анна Сергеевна",
                     "Крылова Ольга Ивановна")


def background_seeds(index: int) -> tuple[Seed, ...]:
    """Один фоновый диалог: чужие люди, чьи подмены и наполняют волт.

    Наполненность — ось прибора, а не декорация: дефект арифметический, и на
    пустом волте всё зелено. Каждый диалог даёт четыре подмены, и их цифры —
    материал, из которого `forge_foreign` строит неизбежное столкновение.
    """
    phone = (f"+7 9{10 + index % 80:02d} {100 + index % 900:03d}-"
             f"{10 + index % 80:02d}-{11 + index % 70:02d}")
    street = _BACKGROUND_STREETS[index % len(_BACKGROUND_STREETS)]
    address = (f"улица {street}, {10 + (index * 7) % 80}, кв. {1 + index % 40}")
    name = _BACKGROUND_NAMES[index % len(_BACKGROUND_NAMES)]
    birth = f"{1 + index % 27:02d}.{1 + index % 12:02d}.19{60 + index % 35}"
    return (
        Seed(role="phone", cue="Телефон клиента: ", value=phone),
        Seed(role="address", cue="Адрес доставки: ", value=address),
        Seed(role="name", cue="Клиент: ", value=name),
        Seed(role="date", cue="Дата рождения: ", value=birth),
    )
