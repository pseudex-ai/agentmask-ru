"""ОДИН интерфейс нотации: «значение в нотации того, кто его написал».

СОДЕРЖИМОЕ ПРИНАДЛЕЖИТ ВОЛТУ, ФОРМА — ОТПРАВИТЕЛЮ. На плече IN ею владеет
КЛИЕНТ: подмена обязана нести его диктовку, регистр, разделители, скрипт и
нотацию чисел. На плече OUT — АГЕНТ: его поверхность, а не наша и не клиента.
И только на плече ИНСТРУМЕНТА нотацию листа объявляет схема (`target`), потому
что инструмент — не человек и фразы не читает.

ЗАЧЕМ ОДНА ТОЧКА, А НЕ СЕМЬ. Дефект класса А («нотация не симметрична») жил не
в умении отрендерить — оно было у PHONE, у даты (`date_form`) и у цифровых
документов, — а в том, что РЕШЕНИЕ о нотации принималось в каждом шве
восстановления своё (вербатимный, токенный, переформатированный, диктовочный,
под-подсказкой, падежный, пофрагментный), а на трёх типах — PLATE, диктовка
LOC и скрипт имени — не принималось вовсе. Отсюда наблюдаемое: агент,
скопировавший подмену дословно, и агент, изменивший в ней один символ, получали
РАЗНЫЕ значения одного поля. Лечение поэтому не «дописать PLATE в
`_atomic_in_form_of`»: пока решений семь, каждая новая нотация (или новый шов)
снова проходит мимо шести из них — ровно это и случилось с PLATE, LOC и
латиницей.

`render_like(value, surface, kind, target=None, for_tool=False)`:
  * `surface` — ОБРАЗЕЦ нотации, то, что написал отправитель;
  * `value`   — СОДЕРЖИМОЕ из волта;
  * `target`  — нотация листа (класс Ж, `FieldSpec`), высший арбитр на плече
    инструмента; без него нотацию держит `surface`;
  * `for_tool` — плечо. Оно меняет ровно одно: инструмент не может исполнить
    продиктованную фразу, поэтому на этом плече диктовка уступает письменной
    (GOST-форме номера, адресу цифрами). Нотацию КЛИЕНТА рендерер не держит
    никогда, кроме прозы, где она и есть ответ.

НИ ОДИН ШОВ НЕ РЕНДЕРИТ САМ: он обязан спросить здесь. Модуль — лист по
импортам (`morph_places`, `date_form`, `spoken`, `agent_form`), потому что его
импортируют и `vault` (минт), и `redact` (оба плеча восстановления).
"""

from __future__ import annotations

import re

from pseudex import agent_form, date_form, morph_places, spoken

# =============================== нотация как класс ===============================

_LATIN = re.compile(r"[A-Za-z]")
_CYRILLIC = re.compile(r"[А-Яа-яЁё]")
_WORD = re.compile(r"[А-Яа-яЁё]{2,}")


def script_of(text: str) -> str:
    """«latin», «cyrillic», «mixed» или «» — СКРИПТ, ось наравне с регистром.

    Диктовка, регистр и разделители уже переносились на часть типов; скрипт не
    переносился ни на один, поэтому `Evgeniy Volnov` получал кириллическую
    подмену, а `A123BC777` — кириллическую. Один вопрос — одна функция.
    """
    latin = bool(_LATIN.search(text))
    cyrillic = bool(_CYRILLIC.search(text))
    if latin and cyrillic:
        return "mixed"
    if latin:
        return "latin"
    if cyrillic:
        return "cyrillic"
    return ""


def case_of(text: str) -> str:
    """Класс регистра целого значения («lower»/«upper»/«title»)."""
    return agent_form.case_class(text)


def looks_dictated(original: str, canonical: str) -> bool:
    """Написанное — это ФРАЗА, произнесённая вслух, а не значение.

    Продиктованный идентификатор — всегда прогон русских слов: «восемь девятьсот
    двадцать шесть…», «ситникова собака мэйл точка ру», «а двести шестьдесят три
    о ка регион шестьдесят шесть». Записанное значение таким не бывает ни у
    одного типа, кроме имени, — а имя решается отдельной ветвью выше.

    Двух слов достаточно и меньше нельзя: одно кириллическое слово встречается
    в написанном адресе («Ленина 14»), а два подряд — только в диктовке.
    """
    if original == canonical:
        return False
    return len(_WORD.findall(original)) >= 2


def notation_of(surface: str, kind: str | None = None) -> str | None:
    """Класс нотации, в котором записано `surface`, или None.

    Единственный ответ на вопрос «как это написано». Тип решает, ЧТО является
    осью: у даты — порядок и разделители компонент (`date_form`), у госномера —
    алфавит × регистр × разделители × диктовка, у адреса — письменная форма или
    диктовка, у имени — регистр × скрипт.
    """
    if not surface:
        return None
    if kind in ("DOB", "DATE"):
        return date_form.notation_of(surface)
    if kind == "PLATE":
        return plate_notation_of(surface)
    if kind in ("LOC", "ADDR"):
        return "place:spoken" if not any(ch.isdigit() for ch in surface) and _WORD.search(surface) else "place:written"
    if kind == "NAME":
        return f"name:{case_of(surface)}:{script_of(surface)}"
    if kind:
        return f"value:{script_of(surface)}:{case_of(surface)}"
    return None


def render_like(value: str, surface: str, kind: str, target: str | None = None,
                for_tool: bool = False) -> str:
    """`value` (содержимое) в нотации `surface` (образец) — или `target`."""
    if not surface:
        return value
    if kind in ("DOB", "DATE"):
        return _date_in_form_of(value, surface)
    if kind == "PLATE":
        return plate_in_form_of(surface, value, for_tool=for_tool, target=target)
    if kind in ("LOC", "ADDR"):
        return place_in_form_of(value, surface, for_tool=for_tool)
    if kind == "NAME":
        return name_in_form_of(value, surface, for_tool=for_tool)
    if kind == "EMAIL":
        local, separator, domain = value.partition("@")
        model_local, model_separator, model_domain = surface.partition("@")
        if separator and model_separator:
            return (agent_form.cased_like(local, model_local) + "@"
                    + agent_form.cased_like(domain, model_domain))
        return value
    # ЦИФРОВЫЕ ДОКУМЕНТЫ — ЭТАЛОН, УЖЕ РАБОТАЮЩИЙ: их рендереры живут в
    # `redact` (там же, где их читает шов), и один из них (`_phone_in_form_of`)
    # отдаёт диктовку словами. Импорт отложенный: `redact` импортирует ЭТОТ
    # модуль, и на уровне модуля получилось бы кольцо. `target` — объявленная
    # схемой нотация листа (класс Ж): единственное, что форсирует нотацию выше
    # поверхности отправителя, и только когда схема её назвала.
    from pseudex.redact import _numeric_in_form_of
    return _numeric_in_form_of(surface, value, kind, target=target or "")


def _date_in_form_of(value: str, surface: str) -> str:
    """Дата: канон (`dd.mm.yyyy`) в нотации образца — эталон класса А."""
    from pseudex import vault
    canonical = vault._date_canonical(value)
    if len(canonical) == 10 and date_form.notation_of(surface) is not None:
        return date_form.render_like(canonical, surface)
    return value


# ================================== ГОСНОМЕР ====================================
#
# ЧТО ЕСТЬ НОТАЦИЯ У НОМЕРА. Четыре группы (буква, три цифры, две буквы, регион)
# и то, КАК они разделены, каким алфавитом и регистром записаны и не сказаны ли
# словами. ГОСТ-канон (`А123ВС777`) — это форма БУМАГИ и валидатора ГИБДД,
# поэтому она и есть нотация листа по умолчанию; нотация КЛИЕНТА сохраняется на
# плече IN целиком, включая диктовку (класс А, решение владельца).
#
# ИНВАРИАНТ, НА КОТОРОМ ДЕРЖИТСЯ ОБРАТИМОСТЬ: письменное зеркало меняет только
# ПРЕДСТАВЛЕНИЕ (регистр, алфавит, разделители) и никогда — буквы и цифры
# содержимого. Иначе подпись содержимого перестала бы находить подмену, а
# неразрешённая подмена в аргументе — это фейк в инструменте клиента.

_LATIN_PLATE = "ABEKMHOPCTYX"
_CYR_PLATE = "АВЕКМНОРСТУХ"
_CYR_TO_LATIN = str.maketrans(_CYR_PLATE + _CYR_PLATE.lower(), _LATIN_PLATE + _LATIN_PLATE.lower())
# СКЛАДЫВАНИЕ ПО ВНЕШНЕМУ СХОДСТВУ — алфавит ГОСТа выбран так, что у каждой
# буквы есть латинский двойник; эта же таблица и есть ТОЖДЕСТВО номера
# (`vault.canonicalize("PLATE", …)` складывает ровно ею).
_LOOKALIKE_TO_CYR = str.maketrans(_LATIN_PLATE + _LATIN_PLATE.lower(), _CYR_PLATE + _CYR_PLATE.lower())

# Четыре группы канона — та форма, которую чеканит `vault._render_token`.
_PLATE_GROUPS = re.compile(r"^([A-Za-zА-Яа-яЁё])(\d{3})([A-Za-zА-Яа-яЁё]{2})(\d{2,3})$")
# Та же форма, как её НАПИСАЛ отправитель: разделители между группами — его.
_PLATE_WRITTEN = re.compile(
    r"^([A-Za-zА-Яа-яЁё])([^0-9A-Za-zА-Яа-яЁё]*)"
    r"(\d{3})([^0-9A-Za-zА-Яа-яЁё]*)([A-Za-zА-Яа-яЁё]{2})"
    r"([^0-9A-Za-zА-Яа-яЁё]*)(\d{2,3})$")
_SEPARATOR = re.compile(r"[ \t,\-]{0,2}")


def plate_content(value: str) -> str:
    """СОДЕРЖИМОЕ номера без нотации: буквы и цифры, склеенные, как в ГОСТе.

    Продиктованный номер проходит через `spoken.plate_from_words` — тот же
    читатель, которым волт канонизирует значение, поэтому второй читалки слов
    здесь не заводится. Письменный — просто без разделителей: регистр и алфавит
    остаются как написаны, их снимет и наложит зеркало.
    """
    dictated = spoken.plate_from_words(value)
    if dictated:
        return dictated
    return re.sub(r"[^0-9A-Za-zА-Яа-яЁё]", "", value)


def plate_signature(surface: str) -> str:
    """Подпись содержимого номера: буквы и цифры, регистр и латиница сняты.

    Тем же приёмом, что цифровая подпись телефона: модель переписывает номер
    (разделители, регистр, латиница), и точная поверхность её больше не называет.

    СКЛАДЫВАЕТСЯ РОВНО ОДНО ЧТЕНИЕ ЛАТИНИЦЫ — ПО ВНЕШНЕМУ СХОДСТВУ, и это то же
    чтение, которым `vault.canonicalize("PLATE", …)` решает «один ли это
    номер». Обе таблицы сразу сложить нельзя, и это не тонкость: звуковая
    читает «H» как «Х», а по внешнему сходству «H» — это «Н», так что
    композиция таблиц отображала бы латинское написание подмены в ДРУГУЮ
    подпись, чем у неё самой (К731НХ616 против K731HX616), и половина
    письменных зеркал перестала бы находиться. ЗВУКОВОЕ написание при этом не
    теряется: оно предлагается отдельной альтернативой точного поиска
    (`redact._restore_tokens_spans`, `_PLATE_SOUND`) — там две читалки одного
    НАПИСАНИЯ безопасны, а в индексе они столкнули бы разные номера.
    """
    return re.sub(r"[^0-9А-ЯЁ]", "", surface.upper().translate(_LOOKALIKE_TO_CYR))


def plate_notation_of(surface: str) -> str | None:
    """Класс нотации номера: диктовка, письменная форма (со своими пробелами)
    или ничего, если это не номер вовсе."""
    if not any(ch.isdigit() for ch in surface):
        return "plate:spoken" if spoken.plate_from_words(surface) else None
    written = _PLATE_WRITTEN.match(surface.strip())
    if written is not None:
        gaps = "/".join(str(len(written.group(index))) for index in (2, 4, 6))
        return f"plate:{script_of(surface)}:{case_of(surface)}:{gaps}"
    return "plate:gost" if _PLATE_GROUPS.match(plate_content(surface)) else None


def plate_in_form_of(surface: str, value: str, for_tool: bool = False,
                     target: str | None = None) -> str:
    """Настоящий номер в нотации `surface`, а на плече инструмента — в ГОСТе.

    Прочитано с двух сторон и это ОДНА функция: на плече IN `surface` — то, как
    номер написал КЛИЕНТ, `value` — подмена из волта; на плече OUT `surface` —
    то, как его написал АГЕНТ, `value` — настоящее значение. Разница только в
    том, чей образец.

    Нотация листа (`target`, класс Ж) на плече инструмента сильнее разделителей
    агента ровно в одном: ГОСТ слитен и заглавен по форме поля ГИБДД. РЕГИСТР И
    АЛФАВИТ остаются агентскими — «форма принадлежит агенту» не перестаёт быть
    правдой от того, что у поля есть форма: поле просит СЛИТНО, не «заглавными
    вместо строчных».
    """
    content = plate_content(value)
    if not content:
        return value
    # ДИКТОВКА: на плече IN диктовка — это и есть нотация источника, которую
    # подмена обязана нести целиком. На плече инструмента фразы не исполняет
    # никто, поэтому там она уступает ГОСТу (ниже).
    if not for_tool and not any(ch.isdigit() for ch in surface) and spoken.plate_from_words(surface):
        words = spoken.plate_in_words_like(content, surface)
        if words is not None:
            return words
    groups = _PLATE_GROUPS.match(content)
    if groups is None:
        # ЧУЖОЙ ТИП (1А, 1Б, 2: «АВ1234 77», «1234 АВ 77»). Наша подмена чеканится
        # одной формой и разделителей такого номера не выражает, поэтому нотацию
        # несёт САМО ЗНАЧЕНИЕ: регистр и алфавит зеркалятся, а раскладка остаётся
        # клиентской. Склеивать её в ГОСТ значило бы менять номер, который
        # валидатор ГИБДД принимает именно так (`test_hard_cases` §plates).
        return _plate_letters_like(value, surface)
    head, digits, pair, region = groups.groups()
    samples = [ch for ch in surface if ch.isalpha()]
    if len(samples) != 3:
        return _plate_cased_like(content, surface)
    letters = _plate_letters((head, pair[0], pair[1]), samples)
    if for_tool or target == "gost":
        gaps = ("", "", "")
    else:
        written = _PLATE_WRITTEN.match(surface.strip())
        gaps = (written.group(2), written.group(4), written.group(6)) if written else ("", "", "")
    return f"{letters[0]}{gaps[0]}{digits}{gaps[1]}{letters[1]}{letters[2]}{gaps[2]}{region}"


def plate_laid_like(original: str, token: str) -> str:
    """Подмена в нотации ИСТОЧНИКА — то, что видит модель на плече IN.

    Отдельное имя, потому что это отдельный вопрос шва («перенеси нотацию»), но
    ответ у него тот же: `plate_in_form_of` с образцом-источником.
    """
    return plate_in_form_of(original, token, for_tool=False)


def _plate_letters(letters: tuple[str, str, str], samples: list[str]) -> tuple[str, str, str]:
    """Буквы подмены в алфавите и регистре образца, позиция за позицией."""
    out: list[str] = []
    for glyph, sample in zip(letters, samples):
        if sample.isascii() and not glyph.isascii():
            glyph = glyph.translate(_CYR_TO_LATIN)
        elif not sample.isascii() and glyph.isascii():
            glyph = glyph.translate(_LOOKALIKE_TO_CYR)
        out.append(glyph.lower() if sample.islower() else glyph.upper())
    return out[0], out[1], out[2]


def _plate_letters_like(value: str, surface: str) -> str:
    """ЗНАЧЕНИЕ в алфавите и регистре образца, буква за буквой, без смены
    раскладки. Для номеров чужого типа (1А/1Б/2) — единственная честная нотация:
    выразить их форму мы не умеем, а переписать чужой номер своей значило бы
    отдать валидатору ГИБДД строку, которой он не знает."""
    samples = [ch for ch in surface if ch.isalpha()]
    letters = [ch for ch in value if ch.isalpha()]
    if not letters or len(samples) != len(letters):
        return value
    out: list[str] = []
    index = 0
    for char in value:
        if not char.isalpha():
            out.append(char)
            continue
        sample = samples[index]
        index += 1
        glyph = char
        if sample.isascii() and not char.isascii():
            glyph = char.translate(_CYR_TO_LATIN)
        elif not sample.isascii() and char.isascii():
            glyph = char.translate(_LOOKALIKE_TO_CYR)
        out.append(glyph.lower() if sample.islower() else glyph.upper())
    return "".join(out)


def _plate_cased_like(content: str, surface: str) -> str:
    """Склейка канона в регистре образца — для образцов, у которых буквы не
    выстраиваются в позиции номера (диктовка, чужой тип 1А/1Б/2)."""
    kind = case_of(surface)
    if kind == "lower":
        return content.lower()
    return content.upper()


# ==================================== АДРЕС =====================================

_NUMBER_ROLES = ("house", "flat", "building", "entrance", "floor")


def written_place(value: str) -> str:
    """Адрес ЦИФРАМИ и с запятыми — то, что исполнит инструмент.

    Продиктованный адрес («гусева восемьдесят один квартира сто семнадцать») —
    это фраза, и в поле доставки она не исполнится ничем. Пересобирается он
    `address_from_fields`, тем же сборщиком, которым волт собирает запись
    по полям, а числа переводит `house_digits` — публичная обёртка над той же
    читалкой числительных, что и везде.
    """
    roles = morph_places.split_roles(value)
    if not roles or not roles.get("street"):
        return value
    fields = {role: (morph_places.house_digits(part) if role in _NUMBER_ROLES else part)
              for role, part in roles.items()}
    if not any(fields.get(role) for role in _NUMBER_ROLES):
        return value
    fields.setdefault("house", "")
    return morph_places.address_from_fields(fields)


def place_in_form_of(value: str, surface: str, for_tool: bool = False,
                     target: str | None = None) -> str:
    """Настоящий адрес в форме, которой пользуется отправитель.

    ПИСЬМЕННЫЙ АДРЕС В ИНСТРУМЕНТЕ ИДЁТ КАК НАПИСАН, и это не уступка, а то же
    правило с другой стороны. `morph_places.in_form_of` вписывает настоящие
    части внутрь строки агента, и для ПЕРЕПИСАННОГО адреса это ровно то, что
    нужно (маршрут `_in_case_of`, он не тронут). Но когда агент скопировал
    подмену ДОСЛОВНО, его строка — наша, а не его, и «вписать» в неё настоящий
    адрес значило бы согласовать его с падежом, которого клиент не писал:
    контроль §4.2 двух адресов («казань зацепская 7 кв 31» → тот же самый текст)
    ровно об этом.

    ДИКТОВАННЫЙ АДРЕС — ДРУГОЕ ДЕЛО, и здесь работает решение владельца: фразу
    инструмент не исполнит ничем, поэтому на плече инструмента она уступает
    письменной форме. Это и есть `LOC spoken` 0/26 у g01: подмена несла диктовку
    источника, агент честно её передал, и в CRM уезжало «гусева восемьдесят один
    квартира сто семнадцать». Решает ВЕЛИЧИНА (то, что лежит в волте), а не
    поверхность: письменное значение уже исполнимо, и переписывать его незачем.
    """
    if not for_tool:
        # ПРОЗА — ЭТО ЗАПИСЬ КЛИЕНТА, и она и есть ответ: его слова, его
        # порядок, его опечатки. Вербатимный шов существует ровно для этого.
        return value
    if not any(ch.isdigit() for ch in value):
        written = written_place(value)
        if written != value and any(ch.isdigit() for ch in written):
            return written
    return value


# ==================================== ИМЯ =======================================

def name_in_form_of(value: str, surface: str, for_tool: bool = False,
                    target: str | None = None) -> str:
    """Настоящее имя в СКРИПТЕ отправителя — регистр решают другие швы.

    СКРИПТ — ТАКАЯ ЖЕ ОСЬ, КАК РЕГИСТР, и до сих пор его не переносил никто:
    `Evgeniy Volnov` получал кириллическую подмену. Переносит `translit`, у
    которого уже есть и таблица по умолчанию, и выученная конвенция модели.

    РЕГИСТР ЗДЕСЬ НЕ ТРОГАЕТСЯ НАМЕРЕННО. У имени регистр решает `agent_form`
    (`name_cased_like`) в тех швах, где известен падеж и порядок частей, а
    вербатимный шов обязан вернуть ЗАПИСЬ КЛИЕНТА как она есть: «Крылов Игорь»
    стоял на месте «иванов петр», и согласовать его с регистром подмены значило
    бы переписать клиента (`test_shown_form_ambiguity`).
    """
    if script_of(surface) == "latin" and script_of(value) != "latin":
        return agent_form.name_cased_like(_latin_words(value), surface)
    return value


def name_in_script(value: str, surface: str) -> str:
    """Подмена-имя в СКРИПТЕ источника, если источник латинский.

    Минт обязан отдать модели то, что она сможет переписать обратно: латинское
    `Evgeniy Volnov` получает латинскую подмену, иначе модель решает, что имя
    другого человека, и агент ведёт себя иначе, чем без нас.
    """
    if script_of(surface) != "latin" or script_of(value) == "latin":
        return value
    rendered = _latin_words(value)
    return agent_form.name_cased_like(rendered, surface) if rendered else value


def _latin_words(name: str) -> str:
    """Имя в латинице, СЛОВО ЗА СЛОВОМ. `translit.render` проводит по таблице
    всю строку и на пробеле теряет его: «Гордей Якушев» возвращалось
    «Gordeiyakushev» — одно слово там, где стояли два, и подмена меняла число
    слов, вокруг которого построена фраза."""
    from pseudex import translit
    return " ".join(translit.render(word, {}) for word in name.split())
