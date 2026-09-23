"""ТЗ §1, §1.1 и §8.4, закреплённые там, где до этого держался только текст.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_spec_form

Этот файл — не второй `test_form.py`. `test_form.py` проверяет СРАВНИТЕЛЬ
против самого себя (пары, метки, воздержание); `test_observe.py` — чтение
хопа. Здесь закреплено ровно то, что ни один из них не мог провалить:

  * СЛОВАРЬ ХОПОВ ПРОТИВ ТЕКСТА ТЗ. `contracts.IN_OWNERS`, `OUT_OWNERS` и
    `MINIMAL_LOOP` списаны сюда из §1 руками, как `test_contracts` списывает
    таблицу признаков §8.4. Без этого K13 требовал ровно тех владельцев,
    которых объявляет сам кортеж, а R07 — ровно `len(MINIMAL_LOOP)` хопов:
    убери «память» из источников или «IN-результат» из петли, и обе проверки
    останутся зелёными, потому что мерили себя.
  * ЧЕТЫРЕ ИСТОЧНИКА И ЧЕТЫРЕ ПОТРЕБИТЕЛЯ, КАЖДЫЙ ПРОЧИТАН. Ветку
    `IN/document` в `observe.observe` не проходил ни один тест пакета, а
    ориентацию `IN/tool`, `OUT/template` и `OUT/summary` не утверждал никто:
    перестановка `produced` и `reference` в `_in_tool` оставляла весь пакет
    зелёным, потому что `form_match` симметричен, а статус считается до.
  * ПОПАРНОЕ СРАВНЕНИЕ КАК ЗАКРЫТОЕ ПРАВИЛО. §8.4: «каждый признак
    извлекается из строки, сравнивается попарно»; R-05 добавляет
    воздержание. Для признака, не объявленного в `FORM_LEXEME_READINGS`,
    вердикт обязан быть РОВНО «метки разные И ни одна не метка
    воздержания» — на матрице строк, а не на выбранных парах. Иначе второй
    сравнитель, добавленный без причины в контракте, не виден ничему.
  * ЖИВОЙ АГЕНТ. §1 меряет форму внутри плеча I на ЖИВОМ агенте; C-003
    требует, чтобы в беговом пути не было скриптового. Требование стояло без
    теста.

Каждая проверка здесь показана красной: доказательства — в отчёте прохода.
"""
import traceback
from collections.abc import Callable
from pathlib import Path

from bench.agentpii4.compare import LevelVerdict, PairVerdict
from bench.agentpii4.schema import PiiItem
from bench.agentpii5 import contracts
from bench.agentpii5.contracts import ArmRunV5, CaseV5
from bench.agentpii5.contracts import FIELD_SEP as SEP
from bench.agentpii5.fixtures import (
    FAKE_NAME,
    REAL_NAME,
    _call,
    _case,
    _hop,
    _in_message,
    _item,
    _result,
    _run,
    _with_calls,
    _with_masked,
    _with_mentions,
    _with_replies,
    _with_results,
    _with_subs,
)
from bench.agentpii5.form import FEATURE_EXTRACTORS, form_match
from bench.agentpii5.observe import observe

# --- §1, списано из ТЗ руками ----------------------------------------------------------
#
# «Источники IN: юзер (сообщение), тул (результат), документ/чанк RAG
# (содержимое), память (раннее упоминание). Потребители OUT: аргумент тула,
# ответ юзеру, сообщение другому агенту/человеку (эскалация, summary), шаблон
# (SMS/письмо).» — порядок тот же, что в контракте, потому что кортеж читают
# как список, а не как множество (отчёт печатает владельцев в его порядке).
SPEC_IN_OWNERS: tuple[str, ...] = ("user", "tool", "document", "memory")
SPEC_OUT_OWNERS: tuple[str, ...] = ("tool_arg", "answer", "template", "summary")
# «Минимальная петля — 4 хопа: IN-юзер → OUT-аргумент → IN-результат → OUT-ответ.»
SPEC_MINIMAL_LOOP: tuple[tuple[str, str], ...] = (
    ("IN", "user"), ("OUT", "tool_arg"), ("IN", "tool"), ("OUT", "answer"))

REAL_PHONE_TEXT: str = "+7 916 123-45-67"


def _name_item(item_id: str) -> PiiItem:
    return _item(item_id, "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(0, 0, len(REAL_NAME)))


def _result_run(case_id: str, tool: str) -> ArmRunV5:
    """Прогон, в котором один результат инструмента нёс реальное имя, а модель
    прочитала подмену на всю его ширину."""
    span = (0, len(REAL_NAME))
    return _with_subs(_with_results(_run(case_id), (_result(
        tool, 0, 0, "single", REAL_NAME, FAKE_NAME, {"p1": span},
        ((span[0], span[1], FAKE_NAME, "NAME"),), False),)), {"p1": FAKE_NAME})


def _in_fixture(owner: str) -> tuple[CaseV5, ArmRunV5]:
    """(кейс, прогон) с ОДНИМ объявленным IN-хопом этого источника.

    Источник несёт реальное имя, модель читает подмену — та самая проверка
    §1: `form(подмена) == form(значение источника)`."""
    if owner == "user":
        hop = _hop("IN", "user", "p1", 0, 0, "", -1, -1, "")
        case = _case("spec-in-user", "single", (REAL_NAME,), (_name_item("p1"),), (hop,))
        return case, _with_subs(_run("spec-in-user"), {"p1": FAKE_NAME})
    if owner == "tool":
        hop = _hop("IN", "tool", "p1", 0, 0, "crm_find_contact", 0, -1, "contacts[].name")
        case = _case("spec-in-tool", "single", ("…",), (_name_item("p1"),), (hop,))
        return case, _result_run("spec-in-tool", "crm_find_contact")
    if owner == "document":
        hop = _hop("IN", "document", "p1", 0, 0, "file_read", 0, -1, "rows[].name")
        case = _case("spec-in-doc", "document", ("…",), (_name_item("p1"),), (hop,))
        return case, _result_run("spec-in-doc", "file_read")
    if owner == "memory":
        hop = _hop("IN", "memory", "p1", 1, 4, "", -1, -1, "")
        case = _case("spec-in-mem", "memory_anaphora", ("…", "…"), (_name_item("p1"),), (hop,))
        run = _with_masked(_with_mentions(_with_subs(_run("spec-in-mem"), {"p1": FAKE_NAME}), (
            contracts.MentionRecord("p1", 0, -1, FAKE_NAME, 1),)),
            {0: ((0, len(REAL_NAME)),), 4: ()})
        return case, run
    raise ValueError(f"нет фикстуры для IN-источника {owner!r}; ТЗ §1 называет {SPEC_IN_OWNERS}")


def _out_fixture(owner: str) -> tuple[CaseV5, ArmRunV5, str, str]:
    """(кейс, прогон, что получил потребитель, что написал агент).

    Агент пишет подмену в СВОЕЙ форме, шлюз кладёт на её место реальное
    значение — проверка §1: `form(реал) == form(подмены, как её написал
    агент)`. Написанное — склонённое: форму агента читают с его вывода, а не с
    канонической подмены."""
    written, restored = "Пахомовой", "Ивановой"
    item = _name_item("p1")
    if owner == "tool_arg":
        hop = _hop("OUT", "tool_arg", "p1", 0, 0, "crm_upsert_contact", 0, -1, "contact.last_name")
        case = _case("spec-out-arg", "single", (REAL_NAME,), (item,), (hop,))
        run = _with_subs(_with_calls(_run("spec-out-arg"), (_call(
            "crm_upsert_contact", {"contact": {"last_name": written}},
            {"contact": {"last_name": restored}}, {}, "", 0),), (0,)), {"p1": FAKE_NAME})
        return case, run, restored, written
    if owner == "template":
        hop = _hop("OUT", "template", "p1", 0, 0, "send_template", 0, -1, "variables.name")
        case = _case("spec-out-tpl", "single", (REAL_NAME,), (item,), (hop,))
        run = _with_subs(_with_calls(_run("spec-out-tpl"), (_call(
            "send_template", {"variables": {"name": written}},
            {"variables": {"name": restored}}, {}, "", 0),), (0,)), {"p1": FAKE_NAME})
        return case, run, restored, written
    if owner == "summary":
        wrote = f"Клиент {written} просит перезвонить"
        got = f"Клиент {restored} просит перезвонить"
        hop = _hop("OUT", "summary", "p1", 0, 0, "escalate_to_human", 0, -1, "summary")
        case = _case("spec-out-sum", "single", (REAL_NAME,), (item,), (hop,))
        run = _with_subs(_with_calls(_run("spec-out-sum"), (_call(
            "escalate_to_human", {"summary": wrote}, {"summary": got}, {}, "", 0),), (0,)),
            {"p1": FAKE_NAME})
        return case, run, got, wrote
    if owner == "answer":
        wrote, got = f"позвоню {written}", f"позвоню {restored}"
        hop = _hop("OUT", "answer", "p1", 0, 0, "", -1, -1, "")
        case = _case("spec-out-ans", "single", (REAL_NAME,), (item,), (hop,))
        run = _with_mentions(_with_subs(_with_replies(_run("spec-out-ans"), wrote, got, ""),
                                        {"p1": FAKE_NAME}),
                             (contracts.MentionRecord("p1", 0, -1, written, 0),))
        return case, run, restored, written
    raise ValueError(f"нет фикстуры для OUT-потребителя {owner!r}; ТЗ §1 называет {SPEC_OUT_OWNERS}")


def test_in_sources_are_the_four_the_spec_names() -> list[str]:
    """§1. Кортеж источников списан из ТЗ, а не выведен из кода.

    K13 требует денominator'а «для каждого владельца из HOP_OWNERS», то есть
    ровно для тех, кого объявляет сам кортеж: выпади «память», и правило
    перестанет её требовать молча."""
    if contracts.IN_OWNERS == SPEC_IN_OWNERS:
        return []
    return [f"IN_OWNERS = {contracts.IN_OWNERS}, ТЗ §1 называет {SPEC_IN_OWNERS}"]


def test_out_consumers_are_the_four_the_spec_names() -> list[str]:
    """§1, та же причина. `template` и `summary` — не украшение: владелец
    решает, в какую строку `form_hOUT` попадёт хоп (`hop_owner_of_leaf`)."""
    if contracts.OUT_OWNERS == SPEC_OUT_OWNERS:
        return []
    return [f"OUT_OWNERS = {contracts.OUT_OWNERS}, ТЗ §1 называет {SPEC_OUT_OWNERS}"]


def test_minimal_loop_is_the_specs_four_hops() -> list[str]:
    """§1. Петля — ПОСЛЕДОВАТЕЛЬНОСТЬ, и её длина — порог R07.

    `MIN_HOPS_WITH_RESULT = len(MINIMAL_LOOP)`, так что укороченная петля
    ослабляет правило корпуса, не тронув ни одного теста схемы: они сравнивают
    длину кейса с той же самой константой."""
    problems: list[str] = []
    if contracts.MINIMAL_LOOP != SPEC_MINIMAL_LOOP:
        problems.append(f"MINIMAL_LOOP = {contracts.MINIMAL_LOOP}, "
                        f"ТЗ §1 называет {SPEC_MINIMAL_LOOP}")
    if contracts.MIN_HOPS_WITH_RESULT != len(SPEC_MINIMAL_LOOP):
        problems.append(f"MIN_HOPS_WITH_RESULT = {contracts.MIN_HOPS_WITH_RESULT}, "
                        f"ТЗ §1 говорит «минимальная петля — {len(SPEC_MINIMAL_LOOP)} хопа»")
    return problems


def test_every_in_source_is_oriented_substitute_against_source() -> list[str]:
    """§1, строка IN: владелец формы — ИСТОЧНИК, проверка —
    `form(подмена) == form(значение источника)`.

    Все четыре источника, по одному кейсу на каждый. Перестановка сторон
    вердикт не двигает (`form_match` симметричен), а статус считается до
    сравнения — поэтому утверждать надо именно `produced`/`reference`, и
    именно этого не делал никто для `tool` и `document`."""
    problems: list[str] = []
    for owner in SPEC_IN_OWNERS:
        case, run = _in_fixture(owner)
        hops = observe(case, run, None, None).hops
        if len(hops) != 1:
            problems.append(f"IN/{owner}: {len(hops)} наблюдений вместо одного — "
                            f"{[one.status for one in hops]}")
            continue
        got = hops[0]
        if got.status != "observed" or got.verdict is None:
            problems.append(f"IN/{owner}: статус {got.status!r}, вердикта нет")
            continue
        if got.produced != FAKE_NAME:
            problems.append(f"IN/{owner}: produced = {got.produced!r}, "
                            f"должна быть подмена {FAKE_NAME!r}")
        if got.reference != REAL_NAME:
            problems.append(f"IN/{owner}: reference = {got.reference!r}, "
                            f"должно быть значение источника {REAL_NAME!r}")
    return problems


def test_every_out_consumer_is_oriented_real_against_written() -> list[str]:
    """§1, строка OUT: владелец формы — АГЕНТ, «форму агента ЧИТАЕМ из его
    вывода».

    Написанное — «Пахомовой», склонённое, а отчеканенная подмена —
    «Пахомова Елена»: reference обязан быть тем, что агент НАПИСАЛ, иначе
    измеряется форма нашего же чекана. Четыре потребителя; `template` и
    `summary` не утверждал никто."""
    problems: list[str] = []
    for owner in SPEC_OUT_OWNERS:
        case, run, received, wrote = _out_fixture(owner)
        hops = observe(case, run, None, None).hops
        if len(hops) != 1:
            problems.append(f"OUT/{owner}: {len(hops)} наблюдений вместо одного — "
                            f"{[one.status for one in hops]}")
            continue
        got = hops[0]
        if got.hop.owner != owner:
            problems.append(f"OUT/{owner}: хоп пришёл как {got.hop.owner!r}")
        if got.status != "observed" or got.verdict is None:
            problems.append(f"OUT/{owner}: статус {got.status!r}, вердикта нет")
            continue
        if got.produced != received:
            problems.append(f"OUT/{owner}: produced = {got.produced!r}, "
                            f"потребитель получил {received!r}")
        if got.reference != wrote:
            problems.append(f"OUT/{owner}: reference = {got.reference!r}, "
                            f"агент написал {wrote!r}")
    return problems


def test_the_hop_reading_does_not_depend_on_the_control_arms() -> list[str]:
    """§1: «сравнение плеч I↔C форму гасит; проверка ВНУТРИ плеча I видит всё».

    `test_metrics.test_form_lines_ignore_controls` держит эту половину на
    МЕТРИКАХ — а `observe` получает `ic`/`cc` в той же сигнатуре и мог бы
    начать их читать одной строкой, до всякой метрики. Здесь закреплено, что
    наблюдения не двигаются, когда парные вердикты v4 приложены."""
    levels = LevelVerdict(tools=True, tools_sub="", keys=True, keys_sub="", state=True,
                          state_verbatim=True, state_diff=(), comparable=frozenset({"state"}))
    problems: list[str] = []
    for owner in SPEC_IN_OWNERS:
        case, run = _in_fixture(owner)
        blind = observe(case, run, None, None).hops
        paired = observe(case, run, PairVerdict("IC", levels, (), ()),
                         PairVerdict("CC", levels, (), ())).hops
        if blind != paired:
            problems.append(f"IN/{owner}: наблюдения изменились, когда приложили вердикты v4")
    if not problems and not any(one.verdict is not None
                                for one in observe(*_in_fixture("user"), None, None).hops):
        problems.append("фикстура не даёт ни одного вердикта — сравнивать было нечего")
    return problems


def test_the_benchmark_run_path_holds_no_scripted_agent() -> list[str]:
    """§0.3/§1: «Агент — живой. Скриптовых агентов нет; детерминирована
    ПРОВЕРКА».

    C-003 требует, чтобы `harness.py` не звал `bench.agentpii4.fake_agent`, и
    до сих пор это проверял только читающий глазами. Читаем ИСХОДНИК, а не
    импортируем: `harness.py` тянет движок, и тест, который его грузит, платит
    за это секундами и правом падать по чужой причине. v4 зовётся целиком
    (`v4_harness` сам импортирует `fake_agent` для своих смоков) — запрещено
    именно обращение ОТСЮДА: `seed_backend_v5`, `run_arm_v5` и живой провайдер
    — единственный путь плеча I."""
    source = Path(__file__).with_name("harness.py").read_text(encoding="utf-8")
    problems: list[str] = []
    for number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")) and "fake_agent" in stripped:
            problems.append(f"harness.py:{number} тянет скриптового агента: {stripped}")
        if "scripted_run" in stripped and not stripped.startswith("#"):
            problems.append(f"harness.py:{number} зовёт скриптовый прогон: {stripped}")
    return problems


# --- §8.4: попарное сравнение как закрытое правило -------------------------------------

# Строки на тип: достаточно разные, чтобы у КАЖДОГО признака нашлась и пара,
# которая совпадает, и пара, которая расходится, и — там, где признак умеет
# воздерживаться — пара, в которой метки разные, а расхождения нет.
STRINGS: dict[str, tuple[str, ...]] = {
    "NAME": ("Иванов Пётр", "иванов пётр", "ИВАНОВ ПЁТР", "Пётр", "Иванов П.",
             "Ivanov Petr", "Иванов-Петров Пётр", "Иванову Петру", "фон Иванов Пётр", "7"),
    "PHONE": (REAL_PHONE_TEXT, "8 916 123-45-67", "+79161234567", "+7 (916) 123-45-67",
              "+7 916 123 45 67", "123"),
    "LOC": ("ул. Ленина, д. 14, кв. 3", "улица Ленина, дом 14, квартира 3", "Ленина 14",
            "Самара, Ленина 14", "Ленина 14, Самара", "ленина 14", "Ленина улица 14",
            "улица Ленина 14", "Ленина 14 корп. 2", "Ленина" + SEP + "14", "14"),
    "DOB": ("14.03.1987", "14/03/87", "14 марта 1987", "4.3.1987", "1987-03-14"),
    "DATE": ("14.03.1987", "14/03/87", "14 марта 1987", "4.3.1987", "1987-03-14"),
    "EMAIL": ("ivan@mail.ru", "Ivan@Mail.ru", "IVAN@MAIL.RU", "@.,"),
    "CARD": ("2200 1234 5678 9010", "2200123456789010", "2200-1234-5678-9010",
             "2200.1234.5678.9010"),
    "SNILS": ("112-233-445 95", "11223344595", "112/233/445 95"),
    "INN": ("7707083893", "770708389312", "7707 083893"),
    "PASSPORT": ("45 09 123456", "4509 123456", "4509123456"),
    "PLATE": ("А123ВС 77", "а123вс 77", "А123ВС77", "123 77"),
}


def _plain_features() -> tuple[tuple[str, str], ...]:
    """Признаки, которые ТЗ §8.4 велит сравнивать попарно — то есть все, кроме
    тех, у кого в `contracts.FORM_LEXEME_READINGS` записана причина не делать
    этого. Список берётся из контракта, а не переписывается: две копии одного
    исключения — это одно исключение, которое однажды разойдётся."""
    return tuple(pair for pair in contracts.feature_pairs()
                 if pair not in contracts.FORM_LEXEME_READINGS)


def test_a_plain_feature_is_decided_by_its_labels_and_the_abstain_rule() -> list[str]:
    """§8.4 + R-05, на матрице, а не на выбранных парах.

    «Каждый признак — булев, извлекается из строки, сравнивается попарно»; R-05
    добавляет ровно одно: признак попадает в `differs`, если метки разные И ни
    одна из сторон не несёт метку воздержания. Для признака без объявленной
    причины (`FORM_LEXEME_READINGS`) вердикт обязан быть РОВНО этим — на всех
    упорядоченных парах строк своего типа.

    Что ловится: второй сравнитель, добавленный без записи в контракте (там
    `differs` перестаёт следовать меткам); потерянная проверка воздержания
    (там «14» снова «согласится» с «Ленина 14» о регистре); экстрактор, который
    `form_match` зовёт не тот, что зарегистрирован."""
    problems: list[str] = []
    for kind, feature in _plain_features():
        extractor = FEATURE_EXTRACTORS[(kind, feature)]
        abstain = contracts.FORM_ABSTAIN.get((kind, feature))
        for produced in STRINGS[kind]:
            for reference in STRINGS[kind]:
                left, right = extractor(produced), extractor(reference)
                expected = left != right and (abstain is None or abstain not in (left, right))
                actual = feature in form_match(kind, produced, reference).differs
                if actual != expected:
                    problems.append(
                        f"{kind}.{feature}({produced!r} vs {reference!r}): метки {left!r}/{right!r}"
                        f"{'' if abstain is None else f', воздержание {abstain!r}'} — "
                        f"{'ждали расхождение, его нет' if expected else 'расхождения быть не должно'}")
    return problems


def test_the_matrix_can_tell_the_rule_from_a_constant() -> list[str]:
    """Проверка выше обязана уметь провалиться по КАЖДОМУ признаку.

    Матрица из одинаковых строк подтвердила бы любое правило: «differs всегда
    пусто» и «differs следует меткам» на ней неразличимы. Поэтому у каждого
    попарного признака должна быть пара, на которой он расходится, и пара, на
    которой он согласен; а у каждого попарного признака с воздержанием — ещё и
    пара с РАЗНЫМИ метками и без расхождения, иначе выброшенная проверка
    воздержания ничего не сдвинет."""
    problems: list[str] = []
    for kind, feature in _plain_features():
        extractor = FEATURE_EXTRACTORS[(kind, feature)]
        abstain = contracts.FORM_ABSTAIN.get((kind, feature))
        pairs = [(extractor(produced), extractor(reference))
                 for produced in STRINGS[kind] for reference in STRINGS[kind]]
        if not any(left != right and (abstain is None or abstain not in (left, right))
                   for left, right in pairs):
            problems.append(f"{kind}.{feature}: в матрице нет пары, на которой он расходится")
        if not any(left == right for left, right in pairs):
            problems.append(f"{kind}.{feature}: в матрице нет пары, на которой он согласен")
        if abstain is not None and not any(left != right and abstain in (left, right)
                                           for left, right in pairs):
            problems.append(f"{kind}.{feature}: в матрице нет пары, где метки разные, "
                            f"а воздержание {abstain!r} гасит расхождение")
    return problems


def test_every_declared_abstention_actually_abstains() -> list[str]:
    """R-05: «список воздержаний — `contracts.FORM_ABSTAIN`, и он нормативен».

    Для признака с СОБСТВЕННЫМ сравнителем `form_match` в этот список не
    смотрит вовсе — решает сравнитель, — и запись живёт ровно настолько,
    насколько сравнитель сам её читает. `name_order_same` читает
    (`FORM_ABSTAIN[("NAME", "order")]`), `name_gram_case_same` — нет: он
    воздерживается по пустому множеству падежей. Поменяй
    `("NAME", "gram_case")` с `unknown` на `nomn` — ни один тест пакета не
    краснел.

    Здесь запись проверяется по СЛЕДСТВИЮ, а не по чтению: если ровно одна
    сторона пары несёт объявленную метку воздержания, расхождения по этому
    признаку быть не должно. Так правило остаётся живым для всех восьми
    записей, включая те три, где сравнитель свой."""
    problems: list[str] = []
    for (kind, feature), abstain in contracts.FORM_ABSTAIN.items():
        extractor = FEATURE_EXTRACTORS[(kind, feature)]
        pairs = [(produced, reference)
                 for produced in STRINGS[kind] for reference in STRINGS[kind]
                 if (extractor(produced) == abstain) != (extractor(reference) == abstain)]
        if not pairs:
            problems.append(f"{kind}.{feature}: в матрице нет строки с меткой {abstain!r} — "
                            f"воздержание нечем проверить")
            continue
        for produced, reference in pairs:
            if feature in form_match(kind, produced, reference).differs:
                problems.append(
                    f"{kind}.{feature}({produced!r} vs {reference!r}): метки "
                    f"{extractor(produced)!r}/{extractor(reference)!r}, одна из них — "
                    f"воздержание {abstain!r}, а расхождение объявлено")
    return problems


_TESTS: tuple[Callable[[], list[str]], ...] = (
    test_in_sources_are_the_four_the_spec_names,
    test_out_consumers_are_the_four_the_spec_names,
    test_minimal_loop_is_the_specs_four_hops,
    test_every_in_source_is_oriented_substitute_against_source,
    test_every_out_consumer_is_oriented_real_against_written,
    test_the_hop_reading_does_not_depend_on_the_control_arms,
    test_the_benchmark_run_path_holds_no_scripted_agent,
    test_a_plain_feature_is_decided_by_its_labels_and_the_abstain_rule,
    test_the_matrix_can_tell_the_rule_from_a_constant,
    test_every_declared_abstention_actually_abstains,
)


def main() -> int:
    failures: list[str] = []
    for test in _TESTS:
        # Упавшая с исключением проверка — КРАСНАЯ проверка, а не конец
        # прогона: отсутствующий экстрактор поднимает KeyError там, где его
        # никто не назовёт, и остановка спрятала бы всё, что за ним. Причина
        # ЗАПИСЫВАЕТСЯ в список провалов (`e2e/lint_tests.py` смотрит на вызов
        # append внутри обработчика, а не на комментарий рядом).
        found: list[str] = []
        try:
            found = test()
        except Exception as error:               # noqa: BLE001 — записывается ниже, не глотается
            frame = traceback.extract_tb(error.__traceback__)[-1]
            found.append(f"поднял {type(error).__name__}: {error} "
                         f"на {Path(frame.filename).name}:{frame.lineno}")
        print(f"  {test.__name__:56} {'ok' if not found else 'FAIL'}")
        failures.extend(f"{test.__name__}: {one}" for one in found)
    print(f"spec_form: {len(_plain_features())} попарных признаков, "
          f"{sum(len(one) for one in STRINGS.values())} строк")
    print("spec_form: PASS" if not failures else "spec_form: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
