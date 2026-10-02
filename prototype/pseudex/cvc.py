"""ВРЕМЕННЫЕ СЕКРЕТЫ: код проверки карты и одноразовый код эмитента.

C1 (O-SECRET, EX-O-SECRET-1). Два класса, оба — короткие прогоны цифр, у
которых НЕТ внутреннего свидетельства: ни контрольной суммы, ни длины, ни
энтропии, которую `credentials.py` уже отверг как признак. Класс делает
СВИДЕТЕЛЬСТВО СНАРУЖИ, и оно ровно такое, каким его назвал контракт C0
(`TYPE-CONTRACTS.json`, `shared_axes` → `context/evidence`):

  * ПЕРВИЧНОЕ — авторитетное имя поля: ключ типизированного KV называет класс
    целиком (`cvc`, `cvv2`, `cid`, `card_code`, `otp`, `sms_code`, …). Карта
    ключей арендуется (`licensing/assets_source.KEY_TYPE`), поэтому классы
    объявлены ТАМ, а не здесь; здесь — их чтение.
  * ВТОРИЧНОЕ — ограниченная подсказка в прозе. Окно подсказки — то же, что у
    всего движка: не больше 20 нецифровых знаков между подсказкой и значением
    (`pseudex/assets.py:432`, `(?i:{cues})\\D{0,20}?({shape})`). Слова подсказок
    тоже арендуются (`assets_source.CTX_TYPES`).

ЗАПРЕЩЕНО ПО ПОСТРОЕНИЮ (и это проверено тестом, а не только записано):
голый прогон цифр любой длины, общая подсказка «код» без уточнения, близость
номера карты (в размеченной популяции выше по потоку — 0 из 77), оценка
энтропии/«похоже на случайное».

ДЛИНА. CARD_VERIFICATION_CODE — ОБЪЯВЛЕННОЕ МНОЖЕСТВО {3, 4}: CVV2/CVC2/CSC
печатают три цифры, CID/4DBC (Amex) — четыре. Фиксированное `\\d{3}` молча
теряет четырёхзначный вариант, неограниченное `\\d{3,4}` расширяет поверхность
ложных срабатываний трёхзначной формы; здесь набор объявлен ПО АЛИАСУ, и
значение, не попавшее в набор, не уходит открытым — оно демотируется в OPAQUE
(`structured.py`, прецедент `_NUMERIC_KEY_TYPES`). ISSUER_OTP — длина НЕ
ОБЪЯВЛЕНА ВООБЩЕ: у C1 нет авторитетного источника (CONTEXT-MATRIX
`known_coverage_gaps`; решение владельца — RESEARCH_GAP → UNASSERTED). Поэтому
весь класс распознаётся ПО ПОЛЮ (имя поля типизирует значение целиком, без
проверки формы) и по подсказке, а подсказка берёт прогон ЦЕЛИКОМ, каким он
написан: никакой длины мы не выдумываем и не объявляем.

ПОДМЕНА. Формат-сохраняющая и только она: 3 цифры → 3 цифры, 4 → 4, OTP —
ширина ИСХОДНИКА. Никогда 16-значная карта (RED-9: `_render_token("CARD")` для
`«314»` чеканит «0162 7271 3505 2316»), никогда `REDACTED<hex>` в числовом поле
(RED-8). Ведущий ноль допустим и переносится (валидности у класса нет, значит
наследуется ровно ЦИФРОВАЯ ФОРМА исходника).

ТОЧЕЧНЫЙ ДОМЕН, И ЭТО ЗАПИСАНО, А НЕ СПРЯТАНО. У трёхзначной подмены 1000
значений. Аргумент `credentials` («коллизия невозможна: сильно больше сотни
бит») сюда не переносится, и обратное отображение по одной только форме
ЗАПРЕЩЕНО: подмену на выходе ищут в ТОМ ЖЕ контексте, который её породил (имя
поля или подсказка), — иначе любой «314» в любом деловом ответе стал бы
кандидатом. Этот остаток (реальное значение, совпавшее со старой подменой) —
развилка O-SECRET-8, владельцем ещё не решённая; он назван в TYPES.md и в
тесте, а не закрыт молчанием.

ПОЧЕМУ НЕ В `vault._token_re`. Формы подмены здесь НЕ добавляются в общий
регулярный распознаватель токенов, и это осознанное отступление от инварианта
«каждая чеканка матчится `TOKEN_RE`» (см. `vault.py:2278`): шаблон `\\b\\d{3}\\b`
сделал бы кандидатом на восстановление КАЖДОЕ трёхзначное число в каждом ответе
модели, а домен в 1000 значений не переживает такой ширины. Класс узнаётся
ТЕМ ЖЕ свидетельством, что и на маскировании (`class_value_spans` ниже), и
разрешается точечным запросом к волту; подмена, которая не разрешилась,
остаётся в ответе и называется остатком (`surviving_substitutes` через
`shown_forms`), а не выдаётся за настоящее значение.
"""

import re
import secrets

from pseudex.assets import ASSETS
from pseudex.detect import Span

CARD_VERIFICATION_CODE = "CARD_VERIFICATION_CODE"
ISSUER_OTP = "ISSUER_OTP"

# THE FAMILY, AS A TUPLE WITH THE ORDER THE REST OF THE ENGINE READS.
LABELS: tuple[str, ...] = (CARD_VERIFICATION_CODE, ISSUER_OTP)
LABEL_SET = frozenset(LABELS)

# Ключ нормализуется так же, как в `structured._KEY_CLEAN_RE` — РАЗДЕЛИТЕЛИ
# УХОДЯТ. Две отдельные нормализации разошлись бы на первом же ключе вида
# `card_cvc`, и разошлись бы молча: карта ключей спрашивается по одной, набор
# длин — по другой.
_KEY_CLEAN_RE = re.compile(r"[\s\-_.]")
_DIGITS_RE = re.compile(r"\D")

# ОБЪЯВЛЕННОЕ МНОЖЕСТВО ДЛИН ПО АЛИАСУ. Это published-грамматика платёжных
# брендов (PCI SSC S1: CAV2/CVC2/CVV2 — три, CID/4DBC — четыре), то есть АЛГОРИТМ,
# а не tuned-словарь: он живёт в движке, как формы документов в `ru_pii.py`.
# Сами ключи — арендуемая лексика и стоят в `assets_source.KEY_TYPE`; тест
# `test_cvc_otp` держит две половины вместе («EVERY leased card-code key
# declares a length»): ключ, который карта типизирует как CVC, но чья длина
# здесь не объявлена, — это КРАСНЫЙ, а не «неизвестно».
CVC_ALIAS_LENGTHS: dict[str, int] = {
    # CVV2 / CVC2 / CSC / CVV / CVC — three digits.
    "cvv": 3, "cvv2": 3, "cvv2code": 3, "cvvcode": 3, "cvvnumber": 3,
    "cvvnum": 3, "cvc": 3, "cvc2": 3, "cvc2code": 3, "cvccode": 3,
    "cvcnum": 3, "csc": 3, "cav2": 3, "cv2": 3, "codecvv": 3, "codecvc": 3,
    "securitycode": 3, "cardsecuritycode": 3, "cardverificationcode": 3,
    "cardverificationvalue": 3, "cvvкод": 3, "кодcvv": 3, "кодcvc": 3,
    "цвс": 3, "цсв": 3, "защитныйкод": 3, "защитныйкодкарты": 3,
    "кодбезопасностикарты": 3, "кодпроверкикарты": 3,
    # CID / 4DBC (American Express) — four digits.
    "cid": 4, "cidcode": 4, "cidnumber": 4, "4dbc": 4, "amexcid": 4,
    "cvv4": 4, "cidкод": 4, "кодcid": 4,
    # THE COMPOUNDS. `card_cvc`/`cardcvc` is the mis-typing RED-9 names: the
    # leased map's prefix-stem fallback reaches the `card` stem first and types a
    # three-digit field as a CARD, so the key arrives here as `cardcvc` and must
    # answer CVC — the authoritative field name is the whole word, not its head.
    "cardcvc": 3, "cardcvc2": 3, "cardcvv": 3, "cardcvv2": 3, "cardcvvcode": 3,
    "cardcode": 3, "cardcid": 4, "card4dbc": 4,
}

# Поля, которые класс НЕ называют, хотя `_key_type` может их сюда привести по
# стему: слова, где «card» — не карта платёжной системы. Список пуст сегодня и
# стоит здесь как место, куда его дописывает ИЗМЕРЕНИЕ, а не догадка; читается
# он один — `field_lengths`.
_CVC_FALSE_FRIENDS: frozenset[str] = frozenset()


def field_lengths(key: str) -> tuple[int, ...]:
    """Объявленные длины значения под ЭТИМ ключом. Пусто — не наш ключ.

    Точное совпадение, затем САМЫЙ ДЛИННЫЙ алиас-префикс: `cvv2code` обязан
    ответить раньше `cvv`, иначе ключ, назвавший вариант, получил бы длину
    головы. Порядок здесь тот же, что у `_key_type`: сначала карта, потом стем.
    """
    normalized = _KEY_CLEAN_RE.sub("", key.strip().lower())
    if normalized in _CVC_FALSE_FRIENDS:
        return ()
    if normalized in CVC_ALIAS_LENGTHS:
        return (CVC_ALIAS_LENGTHS[normalized],)
    best: tuple[int, ...] = ()
    best_size = 0
    for alias, size in CVC_ALIAS_LENGTHS.items():
        if len(alias) > best_size and normalized.startswith(alias):
            best, best_size = (size,), len(alias)
    return best


def is_digit_run(value: str) -> bool:
    """Значение класса — прогон ТОЛЬКО цифр. Разделителей внутри нет."""
    return bool(value) and value.isascii() and value.isdigit()


def leaf_shape_ok(entity_type: str, key: str, value: str) -> bool:
    """Соответствует ли значение ОБЪЯВЛЕННОЙ форме класса под этим ключом.

    CARD_VERIFICATION_CODE: ровно объявленное число цифр для алиаса ключа.
    ISSUER_OTP: ЛЮБОЙ прогон цифр — длины у класса нет, и выдумывать её здесь
    значило бы вернуть в код ровно тот RESEARCH_GAP, который владелец велел
    оставить незакрытым. Значение без цифры или со «смешанным» составом под
    полем, которое называет секрет, — не форма класса; вызывающий обязан
    ПЕРЕТИПИРОВАТЬ его в OPAQUE, а не пропустить (`structured.py`, прецедент
    `_NUMERIC_KEY_TYPES`, RED-5: malformed — маскируется, не пропускается).
    """
    if not is_digit_run(value):
        return False
    if entity_type == CARD_VERIFICATION_CODE:
        return len(value) in field_lengths(key)
    if entity_type == ISSUER_OTP:
        return True
    return False


def key_class(key: str) -> str | None:
    """Класс, который называет ИМЯ ПОЛЯ, или None. Один читатель карты ключей.

    Ключ нормализуется и ищется `structured._key_type` — ТЕМ ЖЕ читателем, что и
    на маскировании, поэтому поле не может быть CVC на входе и чем-то другим на
    выходе.
    """
    if not key:
        return None
    from pseudex import structured
    entity_type = structured.key_type(key)
    return entity_type if entity_type in LABEL_SET else None


def mint(entity_type: str, original: str) -> str:
    """Формат-сохраняющая подмена на те же позиции.

    ШИРИНА — ШИРИНА ИСХОДНИКА И НИКОГДА НЕ ВЫБОР ДВИЖКА: у CVC она уже
    проверена объявленным набором (3 или 4), у OTP её нет вовсе, поэтому берётся
    написанное. Ведущий ноль ИСХОДНИКА принимается (форма класса его допускает),
    но САМА ПОДМЕНА С НУЛЯ НЕ НАЧИНАЕТСЯ, и это не косметика: некавыченное
    числовое поле JSON (`{"cvc": 314}`) маскируется В ТЕКСТЕ, и подмена «042»
    превратила бы объект в `{"cvc": 042}` — невалидный JSON, который модель не
    прочитает, а инструмент не получит. Ноль в первом разряде стоит одно
    значение из десяти и делает это всегда.
    """
    digits = _DIGITS_RE.sub("", original)
    if entity_type == CARD_VERIFICATION_CODE:
        size = len(digits) if len(digits) in (3, 4) else 3
    else:
        # НЕДОСТИЖИМАЯ ВЕТКА, И ЭТО ЗАПИСАНО. Сюда OTP приходит только через
        # `leaf_shape_ok`/подсказку, а обе требуют прогона цифр; вырожденный
        # пустой исходник получает одну цифру, чтобы ни один путь не чеканил
        # пустую строку (пустая подмена — это дыра в тексте, а не подмена).
        size = len(digits) if digits else 1
    head = secrets.choice("123456789")
    tail = "".join(secrets.choice("0123456789") for _ in range(size - 1))
    return head + tail


def _class_candidates(text: str) -> list[tuple[int, int, str, str]]:
    """(start, end, label, value) — значения класса, найденные ТЕМ ЖЕ
    свидетельством, которым их нашёл бы детектор: авторитетное имя поля или
    ограниченная подсказка из арендованной карты.

    Одна функция на оба плеча — маскирование читает поле через `structured`,
    а восстановление обязано спросить ровно то же самое, иначе оно разрешало бы
    подмену по свидетельству, которого детектор не видел, и наоборот.
    """
    found: list[tuple[int, int, str, str]] = []
    if not ASSETS.is_loaded:
        # NO BUNDLE, NO CLASS — the same fail-closed rule the detector follows.
        # Guarded here rather than at each caller because `drop_uncontexted` runs
        # on EVERY detokenisation, and an expired lease must not turn a working
        # unmask path into an exception.
        return found
    # ПОДСКАЗКИ. Скомпилированные арендуемые шаблоны — те же, что читает
    # `ru_pii.detect_structured`; фильтр по нашим меткам, больше ничего.
    for entity_type, pattern in ASSETS.get().ru_pii.ctx_patterns:
        if entity_type not in LABEL_SET:
            continue
        for match in pattern.finditer(text):
            found.append((match.start(1), match.end(1), entity_type, match.group(1)))
    # АВТОРИТЕТНОЕ ИМЯ ПОЛЯ. `detect_structured_kv` — ЕДИНСТВЕННЫЙ читатель
    # карты ключей, поэтому восстановление не может разойтись с маскированием
    # в вопросе «какой ключ что называет». Локальный импорт: `structured`
    # импортирует этот модуль на уровне модуля.
    from pseudex import structured
    for span in structured.detect_structured_kv(text):
        if span.entity_type in LABEL_SET:
            found.append((span.start, span.end, span.entity_type, span.value))
    return found


def detect_spans(text: str) -> list[Span]:
    """Значения класса как спаны — для тестов и для любого вызывающего, кому
    нужен один класс без полного конвейера."""
    return [Span(start, end, label, value)
            for start, end, label, value in _class_candidates(text)]


def restore_spans(text: str, vault, for_tool: bool = False,
                  field_key: str = "") -> list[tuple[int, int, str]]:
    """Подмены класса в тексте агента, разрешённые в настоящие значения.

    КАНДИДАТ — ТОЛЬКО ЗНАЧЕНИЕ В КОНТЕКСТЕ КЛАССА (см. `_class_candidates`), и
    это не осторожность, а арифметика: у трёхзначной подмены домен в 1000
    значений, поэтому «любой прогон цифр» сделал бы кандидатом каждое число в
    каждом деловом ответе. `field_key` — третий вид того же свидетельства: лист
    JSON, отданный сюда ОТДЕЛЬНО от объекта (`unmask_arguments` разбирает
    аргументы по листьям), не несёт ни подсказки, ни фигурных скобок, и имя поля,
    в котором он стоял, — всё, что о нём известно. Значение, не разрешившееся в
    строку ЭТОГО класса, НЕ подменяется: оно остаётся стоять и называется
    остатком (O-SECRET-8).

    Значение возвращается ровно то, что хранит волт (исходное написание), а не
    нормализованное: у класса нет ни разделителей, ни регистра, поэтому
    «форма агента» и «форма клиента» здесь — одни и те же цифры.
    """
    candidates = _class_candidates(text)
    label = key_class(field_key)
    stripped = text.strip()
    if label is not None and is_digit_run(stripped):
        # ЗНАЧЕНИЕ ПОЛЯ ЦЕЛИКОМ — это тоже контекст класса, и он сильнее
        # подсказки: поле названо самим клиентом.
        offset = text.index(stripped)
        candidates.append((offset, offset + len(stripped), label, stripped))
    if not candidates:
        return []
    asked: dict[str, str] = {}
    for _start, _end, candidate_label, value in candidates:
        asked.setdefault(value, candidate_label)
    typed = vault.detokenize_many_typed(set(asked), for_tool)
    spans: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []
    for start, end, candidate_label, value in sorted(
            candidates, key=lambda item: (item[0], -item[1])):
        if any(start < other_end and other_start < end for other_start, other_end in taken):
            continue
        hit = typed.get(value)
        if hit is None or hit[0] != candidate_label:
            continue
        taken.append((start, end))
        spans.append((start, end, hit[1]))
    return spans


def licensed_ranges(text: str, field_key: str = "") -> list[tuple[int, int]]:
    """Участки текста, где класс НАЗВАН: подсказка, авторитетное имя поля, или
    всё значение целиком под полем класса. Одно определение на все входы."""
    ranges = [(start, end) for start, end, _label, _value in _class_candidates(text)]
    label = key_class(field_key)
    stripped = text.strip()
    if label is not None and is_digit_run(stripped):
        offset = text.index(stripped)
        ranges.append((offset, offset + len(stripped)))
    return ranges


def drop_uncontexted(text: str, spans: list[tuple[int, int, str]], vault,
                     for_tool: bool = False, field_key: str = "",
                     ) -> list[tuple[int, int, str]]:
    """Подмена класса, попавшая не под своё свидетельство, НЕ восстанавливается.

    ОБЩИЕ ТОЧЕЧНЫЕ ПРОХОДЫ ВОССТАНОВЛЕНИЯ УЗНАЮТ ПОДМЕНУ ПО СТРОКЕ, А НЕ ПО
    КОНТЕКСТУ: verbatim-проход отдаёт КАЖДУЮ точную копию показанной формы, а
    подписи `token_re`/финансового семейства ловят свободные прогоны цифр в 6–12
    знаков. Для длинной подмены это безопасно — коллизия с деловым числом
    астрономически мала, — а у трёхзначной домен в 1000 значений, поэтому «966» в
    чужом поле стало бы НАСТОЯЩИМ кодом клиента, молча и с кодом 200: ровно
    отказ A7, который владелец ещё не решил (O-SECRET-8). Здесь он не
    разрешается: подмена остаётся стоять и называется остатком
    (`surviving_substitutes`), а не выдаётся за значение.

    НЕ ТРОГАЕТ ЧУЖИЕ ТИПЫ. Спан, чья строка не является подменой этого класса,
    возвращается как был, поэтому телефон, документ и адрес ведут себя ровно
    так, как вели себя до этой правки.
    """
    if not spans:
        return spans
    asked = {text[start:end] for start, end, _ in spans}
    typed = vault.detokenize_many_typed(asked, for_tool)
    licensed = licensed_ranges(text, field_key)
    kept: list[tuple[int, int, str]] = []
    for start, end, value in spans:
        hit = typed.get(text[start:end])
        if hit is None or hit[0] not in LABEL_SET:
            kept.append((start, end, value))
            continue
        if any(low <= start and end <= high for low, high in licensed):
            kept.append((start, end, value))
    return kept


def restore_number_leaf(field_key: str, value: int, vault,
                        for_tool: bool = False) -> int | None:
    """Числовой лист JSON, отданный разбором аргументов как `int`.

    ЗАЧЕМ ОТДЕЛЬНЫЙ ВХОД. `unmask_arguments` разбирает объект и обходит СТРОКОВЫЕ
    листья; число он возвращает как есть, поэтому подмена, отчеканенная в
    НЕКАВЫЧЕННОМ числовом поле (`{"cvc": 314}` — так сериализует короткий код
    собственная система клиента), уезжала инструменту фейком с кодом 200. Здесь
    она разрешается по имени поля — единственному свидетельству, которое у
    изолированного листа осталось.

    ТИП ЛИСТА СОХРАНЯЕТСЯ, и это часть контракта формы (P02). Настоящее значение
    возвращается числом ТОЛЬКО если оно этим же числом и записывается
    (`str(int(real)) == real`): значение с ведущим нулём — «042» — из числового
    поля прийти не могло, и выдать его как `42` значило бы подменить одно
    настоящее значение другим. Такая пара не разрешается и остаётся стоять
    фейком, который называет остаток.
    """
    label = key_class(field_key)
    if label is None or isinstance(value, bool) or value < 0:
        return None
    written = str(value)
    hit = vault.detokenize_many_typed({written}, for_tool).get(written)
    if hit is None or hit[0] != label:
        return None
    real = hit[1]
    if real.isdigit() and str(int(real)) == real:
        return int(real)
    return None
