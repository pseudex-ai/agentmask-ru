"""ТЗ §4, §5, §6, §7, §8.3, §8.5 — утверждения, которые не стерёг никакой тест.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_spec_metrics

ЭТОТ ФАЙЛ НЕ ПОВТОРЯЕТ ЧУЖИЕ ПРОВЕРКИ. Обход среза §4/§5/§6/§7/§8.3/§8.5 нашёл,
что почти всё нормативное уже закреплено — гейт отказа (`test_report_gate`),
фикстуры (`test_fixtures`), знаменатели публичных линий и оси
(`test_metrics`), рубрика и слепота судьи (`test_judge`), пороги калибровки
(`test_calibration`), имена метрик и `Line` (`test_contracts`). Здесь ровно то,
что НИ ОДИН из них не уронил бы:

  * `contracts.DELTA` не читает никто — δ=3pp §4.1 держалась на честном слове
    `bench.agentpii4.report`;
  * `contracts.AXES` никто не сверял со СПИСКОМ срезов §4.2 и агрегатов §4.3:
    `test_report.test_every_axis_prints` перебирает то, что в кортеже лежит, и
    остался бы зелёным на кортеже без `cue`;
  * `metrics.HOP_SLICEABLE` проверен на согласованность с `prints_on_axis`
    (`test_metrics.test_hop_axis_totals_sum`), но не на ПРИСУТСТВИЕ `form_*` и
    `leak` — убери их оттуда, и §4.1/§4.3 печатались бы одной строкой на
    корпус, а суммы по вёдрам сошлись бы тривиально;
  * `JUDGE_MODEL` / `AGENT_MODEL` все тесты берут символом, поэтому «Sonnet —
    судья, Haiku — диалог» (§5) переживало бы любую подмену значения;
  * три из десяти чисел `CALIBRATION` (`holdout_share`, `per_type_min_examples`,
    `recalibrate_on_corpus_change`) не попали в кортеж `test_contracts`;
  * `Line.interval` никто не сверял с Клоппером–Пирсоном — §8.3 называет его
    поимённо, а приближение Вальда прошло бы;
  * `contracts.PUBLISHED` не читает никто: §7 «Публикация (никогда)» была
    комментарием.

Каждая проверка здесь ПОКАЗАНА КРАСНОЙ — ломали то, что она стережёт, и смотрели
на провал. Проверка «функция существует» сюда не входит: она не может упасть.

Нормативные цитаты ТЗ скопированы РУКАМИ, как в `test_contracts.py`, и по той же
причине: смысл в том, что документ и код написаны дважды, а не импортированы
друг из друга.
"""
import ast
import pathlib
import sys
from collections.abc import Callable

from bench.agentpii4 import report as v4_report
from bench.agentpii4.stats import clopper_pearson, zero_failure_floor
from bench.agentpii5 import contracts, judge
from bench.agentpii5.metrics import HOP_AXES, METRIC_FUNCTIONS, prints_on_axis

# ТЗ §4.2, дословно: «срезы: регистры / ярусы имён / cue / семьи / вертикали
# инструментов». Переведено в имена осей один раз, здесь, чтобы расхождение
# читалось как расхождение с документом, а не с чьим-то кортежем.
SPEC_SLICES: dict[str, str] = {
    "register": "регистры",
    "name_tier": "ярусы имён",
    "cue": "cue",
    "family": "семьи",
    "vertical": "вертикали инструментов",
}
# ТЗ §4.3: «агрегаты: по хопу, по типу, по вертикали, по поведению (§3.1)».
SPEC_AGGREGATES: dict[str, str] = {
    "hop_owner": "по хопу",
    "pii_type": "по типу",
    "vertical": "по вертикали",
    "behaviour": "по поведению",
}
# ТЗ §8.3, таблица «метрика | hits / total | фикстуры»: пятнадцать строк. Из них
# `memory_stability` СНЯТА архитектором (J1.2, комментарий об удалении в
# `contracts.METRICS`) — расхождение ТЗ↔код названо в отчёте обхода и здесь не
# чинится; остальные четырнадцать обязаны существовать и быть КРИТЕРИЯМИ
# УСПЕХА, а не подписями. Диагностической ТЗ объявляет ровно одну линию —
# `round_trip_repaired` §4.2 «диагностика, не успех».
SPEC_TABLE_LINES: tuple[str, ...] = (
    "form_hIN", "form_hOUT", "toolresult_masked", "answer_real", "chain_value", "chain_form",
    "multi_all_out", "multi_consistency", "retry_form", "memory_consistency",
    "rag_masked", "rag_identity_kept", "doc_masked", "doc_extracted", "residual")
# ТЗ §4.2, перенесённые из публичного. `rewrite_ratio` и `shared_block` носят в
# коде суффиксы (`_v5` / `_answer`), потому что считают ДРУГИЕ величины —
# решение записано в `contracts.METRICS` и в `test_contracts._spec_metrics`,
# и здесь оно не пере-решается.
SPEC_PUBLIC_LINES: tuple[str, ...] = (
    "leak", "coverage", "typed", "round_trip", "round_trip_repaired", "end_to_end", "overmask",
    "consistency", "stability")

# ТЗ §5, четыре вопроса судьи, дословно: «сопоставил ли агент возвращённую
# запись верно, не выдумал ли, ответил ли на вопрос, учёл ли контекст/память».
# Каждый вопрос опознаётся по слову, которое нельзя выбросить, не изменив
# вопрос: полное совпадение строки запретило бы редактуру формулировки, а
# проверка «вопросов четыре» уже есть в `test_judge` и ничего не говорит о том,
# КАКИЕ они.
SPEC_JUDGE_QUESTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("сопоставил ли запись", ("запись", "оракул")),
    ("не выдумал ли", ("выдумал",)),
    ("ответил ли на вопрос", ("ответил", "вопрос")),
    ("учёл ли контекст/память", ("контекст", "память")),
)

# ТЗ §6: «Д1 форма (хопы) · Д2 tool_result→answer база · Д3 overlap≠coverage ·
# Д4 типы INN/PLATE, clean=6 · Д5 голос/SSE · Д6 разнообразие инструментов ·
# Д7 память/RAG/документы · Д8 тесты корректности метрик». Приборная половина
# каждой дыры — имя линии или оси; Д4 и Д6 — корпус и реестр инструментов, их
# держат `schema.py` / `tools.py` и их тесты, поэтому здесь их нет.
V4_HOLES: dict[str, tuple[str, ...]] = {
    "Д1 форма (хопы)": ("form_hIN", "form_hOUT"),
    "Д2 tool_result→answer база": ("toolresult_masked", "answer_real"),
    "Д3 overlap≠coverage": ("leak", "coverage"),
    "Д5 голос/SSE": ("stream_fidelity",),
    "Д7 память/RAG/документы": ("memory_consistency", "rag_masked", "rag_identity_kept",
                                "doc_masked", "doc_extracted"),
}

PACKAGE_ROOT: pathlib.Path = pathlib.Path(__file__).resolve().parent


def test_no_pseudex() -> list[str]:
    """§7 «Фиксы движка — следующий план». Прибор, импортирующий движок, не
    может провалить движок; этот файл читает только записи и контракты."""
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"движок импортирован: {sorted(bad)}"] if bad else []


def test_tost_delta_is_three_points() -> list[str]:
    """§4.1 «TOST δ=3pp».

    `contracts.DELTA` НЕ ЧИТАЕТ НИКТО в этом пакете — v4 печатает TOST внутри
    своего блока по своей константе, а v5 её только пере-экспортирует. Значит
    обещание «δ=3pp» держалось на том, что никто не тронет v4, и молча уехало
    бы вместе с ним. Проверяется и значение, и ИСТОЧНИК: две константы, которые
    обязаны совпадать, — это одна константа плюс дрейф."""
    problems: list[str] = []
    if contracts.DELTA != 0.03:
        problems.append(f"δ = {contracts.DELTA}, а ТЗ §4.1 называет 3pp")
    if contracts.DELTA != v4_report.DELTA:
        problems.append(f"v5 объявил свою δ ({contracts.DELTA}) помимо v4 "
                        f"({v4_report.DELTA}) — два определения одного порога")
    return problems


def test_public_slices_are_declared() -> list[str]:
    """§4.2 «срезы: регистры / ярусы имён / cue / семьи / вертикали инструментов».

    `test_report.test_every_axis_prints` перебирает `contracts.AXES` и требует
    строку на каждую — то есть проверяет, что напечатано ровно то, что
    объявлено. Про то, ЧТО обязано быть объявлено, не говорит ничего: кортеж
    без `cue` оставил бы его зелёным."""
    problems = [f"ось {axis!r} ({russian}) пропала из contracts.AXES — ТЗ §4.2 её называет"
                for axis, russian in SPEC_SLICES.items() if axis not in contracts.AXES]
    # Отрицательный контроль: тот же поиск обязан НЕ находить ось, которой в
    # кортеже нет, иначе он согласен с любым кортежем.
    if "несуществующая_ось" in contracts.AXES:
        problems.append("поиск принимает ось, которой в контракте нет")
    return problems


def test_form_aggregates_are_declared() -> list[str]:
    """§4.3 «агрегаты: по хопу, по типу, по вертикали, по поведению».

    Ось объявлена — этого мало: `metrics.prints_on_axis` решает, печатается ли
    ЛИНИЯ внутри ведра хоповой оси, и `form_*`, выпавшие из `HOP_SLICEABLE`,
    напечатали бы `AXIS_NOTE` вместо цифры. `test_metrics.test_hop_axis_totals_sum`
    это пропускает по построению: у не-sliceable линии он сумм не сверяет.

    Отрицательный контроль здесь обязателен: `prints_on_axis` возвращает True
    для ЛЮБОЙ линии на не-хоповой оси, поэтому проверка «печатается» без
    линии, которая печататься НЕ должна, зеленела бы на предикате `return
    True`."""
    problems: list[str] = []
    for axis, russian in SPEC_AGGREGATES.items():
        if axis not in contracts.AXES:
            problems.append(f"ось {axis!r} ({russian}) не объявлена — ТЗ §4.3 требует агрегат")
            continue
        for name in ("form_hIN", "form_hOUT"):
            if not prints_on_axis(name, axis):
                problems.append(f"{name} не печатается на оси {axis} ({russian}): "
                                f"агрегат ТЗ §4.3 вышел бы примечанием, а не цифрой")
    # `answer_real` считает ОТВЕТЫ, и хоповая ось посчитала бы один ответ в
    # каждом ведре. Если предикат согласится и на неё — он согласен на всё.
    if prints_on_axis("answer_real", "pii_type"):
        problems.append("предикат пропустил на хоповую ось линию, знаменатель которой — "
                        "не хопы: значит он не различает ничего")
    return problems


def test_leak_slices_by_type_and_register() -> list[str]:
    """§4.1 «`leak` по типу/регистру» — именно эти два среза названы отдельно от
    общего списка §4.2, и держит их та же `HOP_SLICEABLE`."""
    problems: list[str] = []
    for axis in ("pii_type", "register"):
        if axis not in contracts.AXES:
            problems.append(f"ось {axis!r} не объявлена, а §4.1 требует leak по ней")
        elif not prints_on_axis("leak", axis):
            problems.append(f"leak не печатается по оси {axis}")
    # Тот же отрицательный контроль, что и выше, но на leak: если бы предикат
    # пускал на хоповую ось всё подряд, обе строки выше ничего не значили бы.
    if prints_on_axis("residual", "pii_type"):
        problems.append("residual добавляет член на НАБЛЮДЕНИЕ и не может резаться по хопам, "
                        "а предикат его пропустил")
    return problems


def test_spec_table_lines_are_success_criteria() -> list[str]:
    """§8.3 таблица + §4.2 «`round_trip_repaired` (диагностика, **не успех**)».

    Диагностическая линия печатается, но ничего не решает: её отказ не делает
    отчёт НЕПОЛНЫМ (`report.assemble`, `blocked`). Понизить линию §8.3 до
    подписи — значит снять с неё гейт отказа, и ни один тест этого не замечал:
    `test_contracts` сверяет ИМЕНА и требует диагностики только от
    `round_trip_repaired`."""
    problems: list[str] = []
    diagnostic = set(contracts.DIAGNOSTIC_METRIC_NAMES)
    for name in SPEC_TABLE_LINES + SPEC_PUBLIC_LINES:
        if name == "round_trip_repaired":
            continue
        if name not in contracts.METRIC_NAMES:
            problems.append(f"{name}: линия ТЗ §8.3 не объявлена")
        elif name in diagnostic:
            problems.append(f"{name}: линия ТЗ §8.3 объявлена диагностической — "
                            f"её отказ больше не делает отчёт НЕПОЛНЫМ")
    # Отрицательный контроль: множество диагностических не пусто и держит те,
    # что ТЗ так и называет, — иначе проверка выше зеленела бы на `frozenset()`.
    if "round_trip_repaired" not in diagnostic:
        problems.append("round_trip_repaired перестала быть диагностикой (§4.2 «не успех»)")
    return problems


def test_line_is_clopper_pearson_with_the_zero_failure_floor() -> list[str]:
    """§8.3 «`Line(hits, total)` → доля, Клоппер–Пирсон, «сертифицирует ≥» при 100%».

    `test_contracts` проверяет, что `certified` не None при x = n и None при
    промахе, и что пустая линия даёт (0.0, 1.0). Каким ИНТЕРВАЛОМ это считано,
    не спрашивает никто — приближение Вальда прошло бы обе проверки и на
    маленьких знаменателях дало бы интервал уже точного, то есть отчёт,
    обещающий больше, чем измерено."""
    problems: list[str] = []
    for hits, total in ((0, 1), (1, 4), (3, 7), (7, 7), (250, 918)):
        line = contracts.Line("пробная", hits, total)
        if line.interval != clopper_pearson(hits, total):
            problems.append(f"{hits}/{total}: интервал {line.interval} — не Клоппер–Пирсон "
                            f"{clopper_pearson(hits, total)}")
        want = zero_failure_floor(total) if hits == total else None
        if line.certified != want:
            problems.append(f"{hits}/{total}: сертифицирует {line.certified}, ожидалось {want}")
    # Отрицательный контроль: приближение, которое эти проверки обязаны
    # отличать. Без него «интервал равен интервалу» ничего не стоит.
    hits, total = 3, 7
    rate = hits / total
    half = 1.96 * (rate * (1 - rate) / total) ** 0.5
    wald = (max(0.0, rate - half), min(1.0, rate + half))
    if wald == clopper_pearson(hits, total):
        problems.append("сравнение не отличает Вальда от точного интервала")
    return problems


def test_judge_is_sonnet_and_the_dialogue_is_haiku() -> list[str]:
    """§5 и §8.5 «Sonnet — судья, Haiku — диалог (решение владельца)».

    Все тесты пакета берут обе модели СИМВОЛОМ (`contracts.JUDGE_MODEL`), и это
    правильно — так прогон и его отчёт не расходятся. Но ровно поэтому решение
    владельца переживает любую подмену значения: поменяй константу на Haiku, и
    зелёным останется всё, включая проверку `report.calibration_problems`, что
    штамп сделан «той» моделью."""
    problems: list[str] = []
    if "sonnet" not in contracts.JUDGE_MODEL.casefold():
        problems.append(f"судья — {contracts.JUDGE_MODEL!r}, а владелец назвал Sonnet")
    if "haiku" not in contracts.AGENT_MODEL.casefold():
        problems.append(f"диалог ведёт {contracts.AGENT_MODEL!r}, а владелец назвал Haiku")
    if contracts.JUDGE_MODEL == contracts.AGENT_MODEL:
        problems.append("судья и агент — одна модель: судья проверяет собственный ответ")
    return problems


def test_rubric_asks_the_spec_four_questions() -> list[str]:
    """§5 «сопоставил ли агент возвращённую запись верно, не выдумал ли, ответил
    ли на вопрос, учёл ли контекст/память».

    `test_judge.test_rubric_names_four_questions` считает вопросы и требует, что
    все они попали в рубрику; ЧТО они спрашивают, не проверяет никто. Четыре
    вопроса про форму прошли бы его — их остановил бы импортный страж
    `judge.form_words_in`, но четыре вопроса про что угодно ещё не остановило бы
    ничто."""
    problems: list[str] = []
    missing = _questions_missing(judge.RUBRIC_QUESTIONS)
    problems += [f"рубрика не спрашивает «{label}»" for label in missing]
    if len(judge.RUBRIC_QUESTIONS) != len(SPEC_JUDGE_QUESTIONS):
        problems.append(f"вопросов {len(judge.RUBRIC_QUESTIONS)}, а ТЗ §5 называет "
                        f"{len(SPEC_JUDGE_QUESTIONS)}")
    # Отрицательный контроль: тот же матчер на урезанной рубрике обязан назвать
    # выброшенный вопрос. Иначе «ничего не пропало» — утверждение о пустом
    # множестве.
    if not _questions_missing(judge.RUBRIC_QUESTIONS[:-1]):
        problems.append("матчер не заметил выброшенный вопрос — он согласен с любой рубрикой")
    return problems


def _questions_missing(questions: tuple[str, ...]) -> list[str]:
    """Какие из четырёх вопросов ТЗ §5 рубрика не задаёт.

    Вопрос считается заданным, когда ОДНА его строка несёт все опорные слова:
    поиск слов по рубрике целиком склеил бы «ответил» из одного вопроса с
    «вопрос» из другого и объявил бы заданным то, чего нет."""
    folded = [one.casefold() for one in questions]
    return [label for label, words in SPEC_JUDGE_QUESTIONS
            if not any(all(word in text for word in words) for text in folded)]


def test_calibration_constants_the_spec_names() -> list[str]:
    """§8.5: «20% — из holdout», «на каждом типе ПД с ≥ 20 примерами»,
    «Пере-калибровка при … ≥ 20% корпуса».

    Семь из десяти чисел `CALIBRATION` стоят в кортеже `test_contracts`; эти
    три — нет, и поведенческие тесты их не держат: `test_sample_strata` гоняет
    выборку на `holdout_share=0.25`, `test_thresholds` отличает 12 примеров от
    40 (то есть пережило бы порог 15), а `test_recalibration_triggers`
    сравнивает с самой константой и красным станет только при её понижении."""
    cal = contracts.CALIBRATION
    problems: list[str] = []
    if cal.holdout_share != 0.20:
        problems.append(f"доля holdout {cal.holdout_share}, а ТЗ §8.5 называет 20%")
    if cal.per_type_min_examples != 20:
        problems.append(f"порог примеров на тип {cal.per_type_min_examples}, а ТЗ §8.5 — 20")
    if cal.recalibrate_on_corpus_change != 0.20:
        problems.append(f"порог пере-калибровки {cal.recalibrate_on_corpus_change}, "
                        f"а ТЗ §8.5 — 20% корпуса")
    return problems


def test_nothing_reaches_the_public_harness() -> list[str]:
    """§7 «Не входит: Публикация (никогда)».

    `contracts.PUBLISHED` не читает НИ ОДИН модуль и ни один тест: флаг «никогда
    не публикуется» был комментарием. Вторая половина — что пакет не называет
    путь под `public/`: публичный харнесс живёт там, и приватный корпус, дошедший
    до него файлом, публикуется ровно один раз и навсегда.

    Сканируются строковые ЛИТЕРАЛЫ, а не docstring'и: контракт объясняет, где
    живёт публичный харнесс, и запрет на это слово в прозе запретил бы объяснять
    запрет."""
    problems: list[str] = []
    if contracts.PUBLISHED is not False:
        problems.append(f"contracts.PUBLISHED = {contracts.PUBLISHED!r}")
    # Сканер не сканирует СЕБЯ, и это не поблажка: слова, которые он ищет, —
    # его собственный отрицательный контроль ниже и сама строка поиска. Файл,
    # где живёт запрет, обязан уметь его произнести.
    own = pathlib.Path(__file__).resolve()
    for path in sorted(PACKAGE_ROOT.glob("**/*.py")):
        if path.resolve() == own:
            continue
        problems += [f"{path.name}:{line}: путь публичного харнесса в литерале: {text!r}"
                     for line, text in _public_paths(path.read_text(encoding="utf-8"))]
    # Отрицательный контроль: сканер обязан НАХОДИТЬ посаженный литерал, иначе
    # «чисто» означает «сканер ничего не ищет».
    planted = '"""Модуль."""\nOUT = "public/agentmask-ru/corpus.json"\n'
    if not _public_paths(planted):
        problems.append("сканер не заметил посаженный путь под public/")
    if _public_paths('"""Публичный харнесс живёт в public/agentmask-ru."""\n'):
        problems.append("сканер считает находкой прозу docstring'а")
    return problems


def _public_paths(source: str) -> list[tuple[int, str]]:
    """Строковые литералы, называющие публичный харнесс, кроме docstring'ов."""
    tree = ast.parse(source)
    docs: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            docs.add(id(body[0].value))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if id(node) in docs:
            continue
        if "public/" in node.value or "agentmask" in node.value.casefold():
            found.append((node.lineno, node.value[:70]))
    return found


def test_v4_holes_each_have_an_instrument() -> list[str]:
    """§6 «Дыры v4, которые v5 закрывает».

    Дыра закрыта, когда её меряет ЗАРЕГИСТРИРОВАННАЯ линия — объявленная в
    контракте И имеющая функцию. `test_contracts` сверяет имена со своим
    списком, `test_metrics` — регистрацию с контрактом; ни один из двух не знает,
    какая линия какую дыру закрывает, поэтому выпавшая линия читалась бы как
    «список поменяли», а не как «Д7 снова открыта».

    Д4 (типы INN/PLATE, clean=6) и Д6 (разнообразие инструментов) — корпус и
    реестр инструментов; их держат `schema.py` / `tools.py` и их тесты."""
    problems: list[str] = []
    for hole, names in sorted(V4_HOLES.items()):
        for name in names:
            if name not in contracts.METRIC_NAMES:
                problems.append(f"{hole}: линия {name} не объявлена в контракте")
            elif name not in METRIC_FUNCTIONS:
                problems.append(f"{hole}: линия {name} объявлена, но не считается")
    # Д5 — «голос/SSE»: у голоса есть не только линия, но и срез, на котором
    # читается остаток `form_hIN` (Б27). Ось `spoken` — хоповая, и линия формы
    # обязана на ней печататься, иначе срез объявлен и невидим.
    if "spoken" not in HOP_AXES:
        problems.append("Д5: среза «продиктовано/написано» нет среди хоповых осей")
    elif not prints_on_axis("form_hIN", "spoken"):
        problems.append("Д5: form_hIN не печатается по срезу spoken")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("tost_delta_is_three_points", test_tost_delta_is_three_points),
        ("public_slices_are_declared", test_public_slices_are_declared),
        ("form_aggregates_are_declared", test_form_aggregates_are_declared),
        ("leak_slices_by_type_and_register", test_leak_slices_by_type_and_register),
        ("spec_table_lines_are_success_criteria", test_spec_table_lines_are_success_criteria),
        ("line_is_clopper_pearson", test_line_is_clopper_pearson_with_the_zero_failure_floor),
        ("judge_is_sonnet_dialogue_is_haiku", test_judge_is_sonnet_and_the_dialogue_is_haiku),
        ("rubric_asks_the_spec_four_questions", test_rubric_asks_the_spec_four_questions),
        ("calibration_constants_the_spec_names", test_calibration_constants_the_spec_names),
        ("nothing_reaches_the_public_harness", test_nothing_reaches_the_public_harness),
        ("v4_holes_each_have_an_instrument", test_v4_holes_each_have_an_instrument),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print(f"spec metrics: PASS ({len(checks)} проверок)" if not failures
          else "spec metrics: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
