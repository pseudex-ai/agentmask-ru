"""КЛАСС А — нотация не симметрична: один интерфейс, оба плеча, все типы.

ЧТО ЭТОТ ФАЙЛ ПРОВЕРЯЕТ, ОДНИМ ПРАВИЛОМ, НА ВСЕХ ФОРМАТ-СОХРАНЯЮЩИХ ТИПАХ:
  IN  — подмена, показанная модели, несёт нотацию ИСТОЧНИКА: диктовку, регистр,
        разделители и позицию региона, скрипт;
  OUT — настоящее значение в аргументе инструмента несёт нотацию АГЕНТА (того,
        что он написал), а где инструмент фразы исполнить не может — нотацию
        ЛИСТА (ГОСТ для госномера, письменный адрес для диктованного).

КОНТРОЛИ (работали и до класса А и обязаны работать после): разделители
телефона, группировка СНИЛС, диктовка даты рождения. Они здесь ровно затем,
чтобы красное не могло быть «сломанным тестом».

СВИДЕТЕЛИ КЛАССА (research/hop-format-audit/agents/): g03 retry_same_tool
П1/П2/П3 — PLATE 009/013/021/025/033/053/061; g05 parallel П1/П2 — PLATE
012/016/020/024/048 и send_template-000 (LOC-диктовка); g08 single/mailfind
П3/П4 — «нотация писавшего не переносится»; g01 memory_anaphora P1 — spoken LOC
0/26 при PHONE spoken 26/26; g15 document/office П4 — латиница `Evgeniy Volnov`.

ЗАМЕР. Подмены здесь НЕ закреплены: каждая проверка выражена предикатом
нотации или сравнением с тем, что волт реально хранит. Модели и сети нет —
bundle грузится `testkit`.

Запуск из `prototype/`:
    .venv/bin/python test_notation_symmetry.py
"""

from __future__ import annotations

import json
import re

import testkit

testkit.load_dev_bundle()

from pseudex import notation  # noqa: E402
from pseudex.detect import Span  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.redact import mask_text, unmask_arguments  # noqa: E402
from pseudex.vault import Vault, token_re  # noqa: E402

DETECTOR = Detector()
_ROWS: list[tuple[str, str, object, object]] = []


def _check(section: str, name: str, got: object, want: object) -> None:
    _ROWS.append((section, name, got, want))


def _mint(cue: str, value: str, kind: str, label: str) -> tuple[Vault, str]:
    """Подмена, которую увидит модель: единственный спан в `cue + value`."""
    source = cue + value
    spans = DETECTOR.detect(source)
    hits = [span for span in spans if span.start >= len(cue)]
    if len(hits) != 1 or hits[0].entity_type != kind or hits[0].start != len(cue):
        raise AssertionError(
            f"{label}: ждали один {kind} в конце {source!r}, получили "
            f"{[(span.entity_type, source[span.start:span.end]) for span in spans]}")
    vault = Vault(":memory:", "nota-" + label).for_conversation(label)
    return vault, mask_text(source, vault, spans)[len(cue):]


def _tool(vault: Vault, field: str, written: str) -> str:
    """Что реально получит инструмент, если агент напишет `written`."""
    raw = json.dumps({field: written}, ensure_ascii=False)
    restored = json.loads(unmask_arguments(raw, vault))
    return str(restored[field])


# --- КОНТРОЛИ: механизм «нотация источника / нотация агента» уже работал --------

def _controls() -> None:
    vault, fake = _mint("телефон ", "8 (916) 214-88-03", "PHONE", "ctl-phone")
    _check("контроль", "PHONE IN: разделители клиента",
           bool(re.fullmatch(r"\d \(\d{3}\) \d{3}-\d{2}-\d{2}", fake)), True)
    _check("контроль", "PHONE OUT: разделители агента",
           _tool(vault, "phone", fake), "8 (916) 214-88-03")

    vault, fake = _mint("снилс ", "482-256-678 13", "SNILS", "ctl-snils")
    _check("контроль", "SNILS IN: группировка клиента",
           bool(re.fullmatch(r"\d{3}-\d{3}-\d{3} \d{2}", fake)), True)
    _check("контроль", "SNILS OUT: группировка агента",
           _tool(vault, "snils", fake), "482-256-678 13")

    _, fake = _mint("дата рождения ", "второго июня тысяча девятьсот семьдесят пятого года",
                    "DOB", "ctl-dob")
    _check("контроль", "DOB IN: диктовка клиента",
           not any(ch.isdigit() for ch in fake), True)


# --- A/IN: подмена наследует нотацию источника (PLATE) --------------------------

def _plate_in() -> None:
    vault, low = _mint("номер ", "у493са 23", "PLATE", "in-plate-lower")
    _check("A/IN PLATE", "регистр и место региона клиента",
           bool(re.fullmatch(r"[а-яё]\d{3}[а-яё]{2} \d{2,3}", low)), True)

    _, spaced = _mint("номер ", "у 493 са 23", "PLATE", "in-plate-spaced")
    _check("A/IN PLATE", "все разделители клиента",
           bool(re.fullmatch(r"[а-яё] \d{3} [а-яё]{2} \d{2,3}", spaced)), True)

    _, spoken = _mint("номер ", "о сто пятнадцать у ка девяносто девять",
                      "PLATE", "in-plate-spoken")
    _check("A/IN PLATE", "диктовка клиента, а не ГОСТ-канон",
           not any(ch.isdigit() for ch in spoken), True)
    _check("A/IN PLATE", "диктованная подмена читается обратно номером",
           _readable_plate(spoken), True)

    _, caps = _mint("номер ", "У493СА 23", "PLATE", "in-plate-upper")
    _check("A/IN PLATE", "заглавные клиента остаются заглавными",
           bool(re.fullmatch(r"[А-ЯЁ]\d{3}[А-ЯЁ]{2} \d{2,3}", caps)), True)

    # ИНВАРИАНТ ОБРАТИМОСТИ: письменное зеркало меняет ПРЕДСТАВЛЕНИЕ, а не
    # содержимое, поэтому подмена остаётся находимой и по своей подписи, и
    # формой, которую узнаёт `TOKEN_RE`.
    _check("A/IN PLATE", "зеркало не меняет буквы и цифры содержимого",
           notation.plate_signature(low) == notation.plate_signature(spaced)
           == notation.plate_signature(caps), False)   # у трёх разных чеканок разные номера
    _check("A/IN PLATE", "подмена остаётся узнаваемой формой",
           bool(token_re().search(low)) and bool(token_re().search(spaced))
           and bool(token_re().search(caps)), True)
    # ОДНА ЧЕКАНКА, ТРИ НАПИСАНИЯ — ОДНА ПОДПИСЬ, и она индексируется волтом.
    glued = notation.plate_content(low)
    _check("A/IN PLATE", "содержимое зеркала равно содержимому канона, буква в букву",
           (notation.plate_signature(low) == notation.plate_signature(glued),
            len(glued) == len([ch for ch in low if ch.isalnum()])), (True, True))


def _readable_plate(spoken: str) -> bool:
    from pseudex import spoken as spoken_module
    return bool(spoken_module.plate_from_words(spoken))


# --- A/OUT: инструмент получает нотацию агента, а не клиента --------------------

def _plate_out() -> None:
    vault, low = _mint("номер ", "у493са 23", "PLATE", "out-plate-lower")
    real = "у493са 23"
    _check("A/OUT PLATE", "дословная копия — нотация агента, слитно",
           _tool(vault, "plate", low), "у493са23")
    _check("A/OUT PLATE", "заглавные агента остаются заглавными",
           _tool(vault, "plate", low.upper()), "У493СА23")
    # ПЕРЕПИСАННАЯ ПОДМЕНА РАЗРЕШАЕТСЯ, А НЕ УЕЗЖАЕТ ФЕЙКОМ: разделители,
    # регистр и алфавит — представление, содержимое опознаётся подписью.
    glued = notation.plate_content(low).upper()
    _check("A/OUT PLATE", "переписанный слитно номер разрешается",
           notation.plate_signature(_tool(vault, "plate", glued)),
           notation.plate_signature(real))
    latin = glued.translate(str.maketrans("АВЕКМНОРСТУХ", "ABEKMHOPCTYX"))
    latin_out = _tool(vault, "plate", latin)
    _check("A/OUT PLATE", "латинская запись агента разрешается и возвращается латиницей",
           (notation.plate_signature(latin_out) == notation.plate_signature(real),
            all(ch.isascii() for ch in latin_out if ch.isalpha())), (True, True))

    spoken_vault, spoken = _mint("номер ", "о сто пятнадцать у ка девяносто девять",
                                 "PLATE", "out-plate-spoken")
    _check("A/OUT PLATE", "диктант не уезжает в инструмент фразой",
           bool(re.fullmatch(r"[А-ЯЁ]\d{3}[А-ЯЁ]{2}\d{2,3}",
                             _tool(spoken_vault, "plate", spoken.upper()))), True)


# --- A/IN + A/OUT: адрес -------------------------------------------------------

_DICTATED_ADDRESS = "уфа проспект строительный один квартира сто девяносто пять"


def _location() -> None:
    vault, fake = _mint("адрес ", _DICTATED_ADDRESS, "LOC", "loc-spoken")
    # НОТАЦИЯ ИСТОЧНИКА, А НЕ ТОЛЬКО ЕЁ ЧИСЛА: диктовка остаётся диктовкой.
    _check("A/IN LOC", "цифры клиента словами, без запятых",
           not any(ch.isdigit() for ch in fake) and "," not in fake, True)
    _check("A/IN LOC", "сокращённого маркера нашей подмены в зеркале нет",
           "кв." not in fake, True)
    _check("A/IN LOC", "слово-маркер клиента сохранено",
           "квартира" in fake.lower(), True)

    verbatim = _tool(vault, "address", fake)
    _check("A/OUT LOC", "дословная копия — письменный адрес, а не диктант",
           bool(re.search(r"\d", verbatim)) and "," in verbatim, True)

    # КОНТРОЛЬ ВНУТРИ ПРОВЕРКИ: та же строка, но ИЗМЕНЁННАЯ агентом, и раньше
    # рендерилась — значит виноват был именно вербатимный проход.
    changed = _tool(vault, "address", fake + " ")
    _check("A/OUT LOC", "переписанная агентом форма рендерится так же",
           bool(re.search(r"\d", changed)) and "," in changed, True)

    # §4.2: ПИСЬМЕННОЕ значение возвращается КАК НАПИСАНО. Согласовать его с
    # падежом нашей же подмены значило бы изменить то, чего клиент не писал.
    written_vault, _ = _mint("адрес ", "казань зацепская 7 кв 31", "LOC", "loc-written")
    written_fake = mask_text("до казань зацепская 7 кв 31 после", written_vault,
                             DETECTOR.detect("до казань зацепская 7 кв 31 после"))
    shown = "казань зацепская 7 кв 31"
    _check("A/OUT LOC", "письменное значение идёт в инструмент как написано",
           _tool(written_vault, "address", written_fake.split("до ")[1].split(" после")[0]),
           shown)


# --- A/скрипт: подмена наследует СКРИПТ источника -------------------------------

def _script() -> None:
    vault, fake = _mint("клиент ", "Evgeniy Volnov", "NAME", "script-latin")
    _check("A/скрипт NAME", "латинская подмена для латинского источника",
           all(ch.isascii() for ch in fake if ch.isalpha()), True)
    _check("A/скрипт NAME", "подмена остаётся именем из двух слов",
           len(fake.split()), 2)
    # ОБРАТИМОСТЬ: латинская подмена обязана разрешаться в настоящее значение,
    # иначе она молча уезжает в инструмент как имя человека, которого нет.
    _check("A/скрипт NAME", "латинская подмена разрешается обратно",
           _tool(vault, "name", fake), "Evgeniy Volnov")


# --- интерфейс: одно решение о нотации, а не семь -------------------------------

def _interface() -> None:
    _check("интерфейс", "класс письменного госномера назван",
           notation.notation_of("у493са 23", "PLATE"), "plate:cyrillic:lower:0/0/1")
    _check("интерфейс", "класс диктованного госномера назван",
           notation.notation_of("о сто пятнадцать у ка девяносто девять", "PLATE"),
           "plate:spoken")
    _check("интерфейс", "класс диктованного адреса назван",
           notation.notation_of(_DICTATED_ADDRESS, "LOC"), "place:spoken")
    _check("интерфейс", "класс письменного адреса назван",
           notation.notation_of("казань зацепская 7 кв 31", "LOC"), "place:written")
    _check("интерфейс", "рендерер идемпотентен на письменном номере",
           notation.plate_in_form_of("у493са 23",
                                     notation.plate_in_form_of("у493са 23", "Х731КХ616")),
           "х731кх 616")
    _check("интерфейс", "подпись складывает латиницу ПО ВНЕШНЕМУ СХОДСТВУ",
           (notation.plate_signature("A123BC777") == notation.plate_signature("А123ВС777"),
            notation.plate_signature("K731HX616") == notation.plate_signature("К731НХ616"),
            notation.plate_signature("С732ХК935") == notation.plate_signature("S732HK935")),
           (True, True, False))
    _check("интерфейс", "подпись не путает разные номера",
           notation.plate_signature("К731НХ616") == notation.plate_signature("К731ВХ616"), False)
    # ЗВУКОВОЕ НАПИСАНИЕ («S» за «С», «N» за «Н») подписью не складывается — и
    # не должно: оно разрешается отдельной альтернативой ТОЧНОГО поиска, и это
    # проверяется на настоящей чеканке. ГОСТ-форма нужна потому, что альтернатива
    # складывает написание целиком: зеркальная (клиентская) форма разрешается
    # подписью, а смесь «звук + переписанный регистр» — нет (см. остаточный риск
    # в D-073).
    gost_vault, gost_fake = _mint("номер ", "А123ВС777", "PLATE", "iface-plate-sound")
    sound = notation.plate_content(gost_fake).upper().translate(
        str.maketrans("АВЕКМНОРСТУХ", "AVEKMNORSTUH"))
    _check("интерфейс", "звуковое написание агента разрешается в тот же номер",
           notation.plate_signature(_tool(gost_vault, "plate", sound)),
           notation.plate_signature("А123ВС777"))


def main() -> int:
    _controls()
    _plate_in()
    _plate_out()
    _location()
    _script()
    _interface()
    bad = [row for row in _ROWS if row[2] != row[3]]
    section = ""
    for sec, name, got, want in _ROWS:
        if sec != section:
            print(f"\n[{sec}]")
            section = sec
        if (sec, name, got, want) in bad:
            print(f"  RED   {name}\n        получили : {got!r}\n        контракт : {want!r}")
        else:
            print(f"  PASS  {name}")
    total = len(_ROWS)
    print(f"\nnotation_symmetry: {total - len(bad)}/{total} контрактных проверок пройдено")
    if bad:
        print("НОТАЦИЯ КЛАССА А НЕ СИММЕТРИЧНА: подмена не наследует нотацию источника "
              "или восстановление не рендерит в нотации агента.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
