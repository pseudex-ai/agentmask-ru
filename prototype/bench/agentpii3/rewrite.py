"""Что настоящая модель делает с подменой, прежде чем положить её в аргумент.

ЗАЧЕМ ЭТОТ ФАЙЛ СУЩЕСТВУЕТ. Офлайновая ось 2 принимала модель ИДЕАЛЬНОЙ: где
шлюз подменил — она копирует подмену ДОСЛОВНО. Допущение выглядело осторожным
(мы не выдумываем за модель) и на деле сделало прибор слепым к самому крупному
классу дефектов: живой прогон 400 диалогов показал 58.6% возврата там, где
офлайн печатал 76.9%, и вся разница — в том, что модель подмену НЕ КОПИРУЕТ.

Она делает с ней ровно две вещи, и обе видны в `bench/runs/2026-09-01`:

  ПЕРЕФОРМАТИРУЕТ. «улица Тополиная, 49» приходит как «ул. Тополиная, д. 49»,
  «улица Тополиная, дом 49», «Тополиная, 49». 35 из 43 вердиктов
  `substitute_shown` — это агент, подтверждающий адрес клиенту своими словами.

  РАЗБИРАЕТ ПО ПОЛЯМ. Схема инструмента просит `street`, `house`, `entrance`
  отдельно, и модель раскладывает подмену по ним. 50 из 54 `not_resolved`.

ПРЕОБРАЗОВАНИЯ ВЗЯТЫ ИЗ ПРОГОНА, А НЕ ПРИДУМАНЫ. Каждое ниже сопровождается
случаем, в котором оно наблюдалось живьём. Придуманное преобразование сделало
бы прибор строже настоящей модели, и тогда мы чинили бы то, чего в поле нет.

ВЫБОР ДЕТЕРМИНИРОВАН. Ключ — (case_id, argument), поэтому два прогона одного
корпуса дают одни и те же строки и числа сравнимы побитово. Случайность здесь
означала бы, что «ось 2 гуляет» перестало быть свойством чеканки подмен и стало
свойством прибора.
"""
import hashlib
import re

# Родовые слова адреса и их сокращения — ровно те, что встречаются в подменах
# `_fake_place` и в ответах модели.
_LONG_TO_SHORT = {
    "улица": "ул.", "улицу": "ул.", "улице": "ул.", "улицы": "ул.",
    "проспект": "просп.", "проспекте": "просп.", "проспекта": "просп.",
    "переулок": "пер.", "переулке": "пер.", "переулка": "пер.",
    "шоссе": "ш.", "бульвар": "б-р", "бульваре": "б-р",
    "набережная": "наб.", "площадь": "пл.",
}

# Разбор подмены на части. Подмены чеканит `vault._fake_place`, и форм всего
# три: «улица Тополиная 49», «Тополиный проспект 49», «Сортавала, улица
# Тополиная 65, кв. 136». Разбор устроен по этим формам, а не по общей
# адресной грамматике: он обслуживает ПРИБОР, и лишняя общность здесь означала
# бы, что прибор умеет больше, чем то, что он моделирует.
_CITY_HEAD = re.compile(r"^([А-ЯЁ][а-яё\-]+),\s+")
_FLAT_TAIL = re.compile(r",?\s*(?:кв\.?|квартира)\s*(\d{1,4})\s*$", re.IGNORECASE)
_HOUSE_TAIL = re.compile(r",?\s+(\d{1,4}(?:/\d{1,3})?[а-яё]?)\s*$", re.IGNORECASE)


def split_address(phrase: str) -> dict[str, str]:
    """Подмена, разложенная на роли: city / street / house / flat.

    Возвращает только те роли, которые в строке ЕСТЬ. Отсутствующая роль — не
    ошибка: у подмены нет подъезда, потому что генератор его не чеканит, и
    модель в поле `entrance` берёт что-то своё. Прибор обязан показать это как
    отсутствие, а не подставить туда целую фразу.
    """
    rest = phrase.strip()
    out: dict[str, str] = {}
    city = _CITY_HEAD.match(rest)
    if city:
        out["city"] = city.group(1)
        rest = rest[city.end():]
    flat = _FLAT_TAIL.search(rest)
    if flat:
        out["flat"] = flat.group(1)
        rest = rest[:flat.start()]
    house = _HOUSE_TAIL.search(rest)
    if house:
        out["house"] = house.group(1)
        rest = rest[:house.start()]
    street = rest.strip().strip(",")
    if street:
        out["street"] = street
    return out


# Роль поля выводится из ИМЕНИ аргумента, а не из формы значения. Схемы корпуса
# называют поля прямо (`street`, `pickup_house`, `dropoff_flat`), и имя — это
# то единственное, что модель тоже видит, когда решает, что куда положить.
_ROLES = ("street", "house", "flat", "entrance", "city", "apartment", "building")


def role_of(argument: str) -> str:
    """Роль поля схемы, если она читается из имени. Иначе пустая строка."""
    parts = argument.lower().split("_")
    for role in _ROLES:
        if role in parts:
            return {"apartment": "flat", "building": "house"}.get(role, role)
    return ""


def _pick(key: str, options: list[str]) -> str:
    """Детерминированный выбор варианта по ключу случая."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return options[digest[0] % len(options)]


def reformat_address(phrase: str, key: str) -> str:
    """Адресная подмена в том виде, в каком её ПЕРЕПИШЕТ модель.

    Наблюдалось живьём (`bench/runs/2026-09-01/live-medium`):

      cmp-same-023          'ул. Рябиновая, 88'        сокращение родового слова
      wordnum-naked-034     'улица Ольховая, дом 126'  вставка «дом»
      crowd-orderer-026     'улица Каштановая, дом 14, квартира 86'
      wordnum-two_points-110 'Барбарисовая'            родовое слово опущено
      direct-0075           'переулок Мятный, д. 93, кв. 1200'

    «Как есть» остаётся одним из вариантов: модель нередко копирует дословно, и
    прибор, который переписывает ВСЕГДА, преувеличил бы дефект ровно так же,
    как прежний преувеличивал качество.
    """
    parts = split_address(phrase)
    street = parts.get("street", "")
    if not street:
        return phrase
    words = street.split()
    generic = next((word for word in words if word.lower() in _LONG_TO_SHORT), "")
    short = _LONG_TO_SHORT.get(generic.lower(), "")

    def rebuild(street_text: str, house_marker: str, flat_marker: str) -> str:
        out = street_text
        if "house" in parts:
            out += f", {house_marker}{parts['house']}" if house_marker else f", {parts['house']}"
        if "flat" in parts:
            out += f", {flat_marker}{parts['flat']}"
        if "city" in parts:
            out = f"{parts['city']}, {out}"
        return out

    variants = [phrase, rebuild(street, "", "кв. ")]
    if short:
        variants.append(rebuild(street.replace(generic, short), "", "кв. "))
        variants.append(rebuild(street.replace(generic, short), "д. ", "кв. "))
    variants.append(rebuild(street, "дом ", "квартира "))
    if generic and len(words) > 1:
        bare = " ".join(word for word in words if word != generic)
        variants.append(rebuild(bare, "", "кв. "))
    return _pick(key, variants)


def decompose_for_role(phrase: str, argument: str) -> str:
    """Часть подмены, которую модель положит в ЭТО поле схемы.

    Пустая строка означает «у подмены нет такой части» — например подъезда,
    которого генератор не чеканит. Вызывающий обязан отличить это от «часть
    есть и она такая»: подставить туда всю фразу значило бы утверждать, что
    модель кладёт весь адрес в поле `entrance`, а живой прогон показывает
    обратное (она кладёт туда выдуманное число).
    """
    role = role_of(argument)
    if not role:
        return phrase
    return split_address(phrase).get(role, "")


def name_part(substitute: str, whole: str, expected: str) -> str:
    """Часть ИМЕННОЙ подмены, соответствующая запрошенной части настоящего имени.

    Здесь работает индекс слова, а не роль: «Ярослав Максимович Жуков» и
    «ярослав максимович жуков» состоят из одинакового числа слов, и `surname`
    в схеме — это третье слово там и третье слово здесь. Для адреса так нельзя
    («заречная сорок пять второй подъезд» — пять слов против трёх у подмены),
    поэтому адрес разбирается по ролям, а имя — по позиции.

    Живьём: ctx-q19-long — модель написала «Ярослава» от подмены
    «Ярослав Максимович Жуков»; ctx-q09-short — «Капитолины» от «Капитолине
    Сазонову».
    """
    real_words = whole.split()
    fake_words = substitute.split()
    want = expected.split()
    if not want or len(real_words) != len(fake_words) or len(want) >= len(real_words):
        return substitute
    lowered = [word.lower().strip(".,") for word in real_words]
    try:
        start = lowered.index(want[0].lower().strip(".,"))
    except ValueError:
        return substitute
    return " ".join(fake_words[start:start + len(want)])
