"""ПРОГОН КАК ОБЪЕКТ: оценка до запуска, реестр прогонов, стоп-кран по цене.

    python3 -m bench.agentpii5.runinfo list
    python3 -m bench.agentpii5.runinfo show <run id>

`docs/tz-bench-harness.md` §1 и §7.1 (пункты 1, 2, 3, 4, 20). Ничего здесь не
считает метрику и не читает запись плеча: этот модуль знает только ЧТО стоил
прогон, чем он был помечен и на что похож следующий.

ТРИ ПРАВИЛА, ИЗ КОТОРЫХ ВЫВЕДЕНО ВСЁ ОСТАЛЬНОЕ.

1. **Реестр аддитивен.** `append_run` дописывает строку и отказывается
   переписать уже записанную: прогон — событие, а не поле, которое правят
   задним числом. Прерванный прогон остаётся в реестре прерванным, потому что
   «прогон, о котором мы молчим» и «прогона не было» неразличимы через месяц.

2. **В реестре нет ни ключа, ни значения из корпуса.** Метка и заметка —
   свободный текст человека; `refuse_secrets` и `refuse_corpus_values`
   отказывают ДО прогона, пока отказ ничего не стоит. Но свободный текст
   приезжает в строку и ПОСЛЕ трат — вердикт отчёта, а у прерванного прогона
   ещё и текст исключения, который несёт всё, что было в сообщении об ошибке
   (адрес с ключом в строке запроса, значение, на котором упал разбор). Там
   отказывать нельзя: отказ на этом конце стирает строку прогона, который уже
   заплатил (§1.2 требует обратного). Поэтому те же два правила применяются
   ВЫЧИСТКОЙ (`scrub_free_text`) к каждому свободному полю
   (`FREE_TEXT_FIELDS`), и вычистка ГОВОРИТ о себе в тексте, а не молчит.
   Реестр лежит в репозитории и переживёт корпус.

3. **Оценка называет своё основание.** Число без основания («$14») читается
   как измерение; интервал с подписью «по последнему medium той же пары
   моделей» читается как то, чем он является. Основания упорядочены, и когда
   ни одного прошлого прогона нет, оценка честно говорит, что нижней границы
   нет, а верхняя — зарезервированный потолок.

ЭТОТ МОДУЛЬ НЕ ИМПОРТИРУЕТ ДВИЖОК И НЕ ИМПОРТИРУЕТ `bench.agentpii4.harness`
(который тянет `bench.agentpii3.live.judge`, а тот — движок). Поэтому резерв
потолка приходит сюда ЧИСЛОМ, а не вычисляется здесь через `v4.cap_usd`:
оценка должна считаться на машине без бандла, без ключей и без сети.
"""
import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

from bench.agentpii4.writer import WriterError
from bench.agentpii5 import records as r
from bench.agentpii5.connectors import ConnectorError
from bench.agentpii5.contracts import CaseV5, INCOMPLETE_REPORT_MARK


class RunInfoError(ValueError):
    """Строка реестра, которую нельзя ни записать, ни прочитать как запись.

    Несёт поле и найденное значение: реестр правится руками (только `eol`-подобные
    поля — метка и заметка), и отказ обязан называть, что именно не так.
    """


# --- §1.2 реестр прогонов -------------------------------------------------------------------

# Имя файла — константа, потому что его называют три читателя (харнесс, CLI
# этого модуля и будущий `trend`), а третье написание имени — это реестр,
# которого никто не увидит.
RUNS_FILE: str = "runs.json"
# И ЕГО ПУТЬ — ТОЖЕ ЗДЕСЬ. Реестр один на пакет, а `here / RUNS_FILE` считали у
# себя харнесс, `trend` и `repro` (последний брал константу из `trend` — модуля,
# который к файлу никакого отношения не имеет). Три вычисления одного пути — это
# три шанса разойтись на первом же переезде каталога, и разойдутся они молча:
# пустой реестр читается как «прогонов не было».
RUNS_PATH: Path = Path(__file__).resolve().parent / RUNS_FILE
RUNS_VERSION: int = 1
# Состояния прогона. Закрытый словарь: «прерван» — не свободный текст, по нему
# фильтрует и оценка (основанием может быть только ЗАВЕРШЁННЫЙ прогон), и
# карантин (пункт 21, чужой).
RUN_STATES: tuple[str, ...] = ("finished", "interrupted")


@dataclass(frozen=True)
class RunRecord:
    """Одна строка `runs.json` — ровно поля §1.2 ТЗ.

    `worktree` — состояние рабочего дерева (§6.1). Здесь это СТРОКА, которую
    пишет тот, кто её знает (дисциплина живёт в другом месте), а не вычисление:
    модуль, который сам запускает `git`, нельзя прогнать на копии каталога
    прогона, а именно так реестр и читают.

    `verdict` — вердикт отчёта («полный» / «НЕПОЛНЫЙ: …»), не вердикт метрики.
    """

    run_id: str
    benchmark: str
    started: str                 # ISO 8601 UTC
    finished: str                # ISO 8601 UTC — когда строка записана
    state: str                   # RUN_STATES
    tier: str
    cases: int                   # выбранных случаев (без умножения на повторы)
    repeats: int
    triples_done: int
    transport_terminated: int    # §1.4: случаи, снятые обрывом провайдера
    model: str
    judge_model: str
    concurrency: int
    corpus_digest: str
    ladder_digest: str
    label: str
    note: str
    ceiling_usd: float
    spent_usd: float
    wall_s: float
    verdict: str
    worktree: str
    run_dir: str
    # §4.1 И §4.2 В РЕЕСТРЕ, А НЕ ТОЛЬКО В `meta.json`. ТЗ просит цены и шлюз в
    # ОБОИХ файлах, и причина не в симметрии: `meta.json` лежит в каталоге
    # прогона, который стирают, переносят и переименовывают, а реестр — то
    # единственное, что остаётся в репозитории. Строка, по которой нельзя
    # переоценить прогон в сегодняшних деньгах и нельзя сказать, что маскировало,
    # через год стоит ровно столько же, сколько строка без метки.
    #
    # ЗНАЧЕНИЕ ПО УМОЛЧАНИЮ ЗДЕСЬ — ОСОЗНАННОЕ ИСКЛЮЧЕНИЕ. Блок собирает
    # `provider.run_block`, и он есть у каждого ПЛАТНОГО прогона; фикстуры
    # читателей реестра (`test_trend`, `test_repro`) строят строку без него, и
    # требовать его от них значило бы выдумать провайдера там, где никакая модель
    # не отвечала. Читатель (`run_record_from_json`) КЛЮЧ требует: строку на
    # диске всегда пишет `run_record_to_json`, и пустой словарь в ней — это
    # «прогон не назвал провайдера», а не «поле потерялось».
    provider: dict[str, object] = field(default_factory=dict)
    gateway: dict[str, object] = field(default_factory=dict)


_FIELD_ORDER: tuple[str, ...] = (
    "run_id", "benchmark", "started", "finished", "state", "tier", "cases", "repeats",
    "triples_done", "transport_terminated", "model", "judge_model", "concurrency",
    "corpus_digest", "ladder_digest", "label", "note", "ceiling_usd", "spent_usd",
    "wall_s", "verdict", "worktree", "run_dir", "provider", "gateway")


def run_record_to_json(record: RunRecord) -> dict[str, object]:
    """Строка на диск. Порядок полей фиксирован `_FIELD_ORDER`, чтобы diff
    реестра показывал изменение значения, а не перестановку ключей."""
    row: dict[str, object] = {
        "run_id": record.run_id, "benchmark": record.benchmark, "started": record.started,
        "finished": record.finished, "state": record.state, "tier": record.tier,
        "cases": record.cases, "repeats": record.repeats, "triples_done": record.triples_done,
        "transport_terminated": record.transport_terminated, "model": record.model,
        "judge_model": record.judge_model, "concurrency": record.concurrency,
        "corpus_digest": record.corpus_digest, "ladder_digest": record.ladder_digest,
        "label": record.label, "note": record.note,
        "ceiling_usd": round(record.ceiling_usd, 6), "spent_usd": round(record.spent_usd, 6),
        "wall_s": round(record.wall_s, 1), "verdict": record.verdict,
        "worktree": record.worktree, "run_dir": record.run_dir,
        "provider": dict(record.provider), "gateway": dict(record.gateway)}
    return {key: row[key] for key in _FIELD_ORDER}


def _text(row: dict[str, object], key: str) -> str:
    """Строковое поле или отказ по имени.

    Читатели `records.py` устроены так же и по той же причине (`row.get(key,
    "")` превращает дефект писателя в пустую метку, которую никто не заметит),
    но НЕ переиспользуются: они поднимают `RecordError` про запись прогона, а
    здесь речь о строке реестра, и подменять одно другим значило бы врать в
    тексте отказа.
    """
    if key not in row:
        raise RunInfoError(f"RunRecord: нет поля {key!r}; в строке {sorted(row)}")
    value = row[key]
    if not isinstance(value, str):
        raise RunInfoError(f"RunRecord.{key}: ожидалась строка, найдено "
                           f"{type(value).__name__} {value!r}")
    return value


def _whole(row: dict[str, object], key: str) -> int:
    if key not in row:
        raise RunInfoError(f"RunRecord: нет поля {key!r}; в строке {sorted(row)}")
    value = row[key]
    # `bool` — подкласс `int`, и «True случаев» прочиталось бы как 1.
    if not isinstance(value, int) or isinstance(value, bool):
        raise RunInfoError(f"RunRecord.{key}: ожидалось целое, найдено "
                           f"{type(value).__name__} {value!r}")
    return value


def _amount(row: dict[str, object], key: str) -> float:
    if key not in row:
        raise RunInfoError(f"RunRecord: нет поля {key!r}; в строке {sorted(row)}")
    value = row[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RunInfoError(f"RunRecord.{key}: ожидалось число, найдено "
                           f"{type(value).__name__} {value!r}")
    return float(value)


def _block(row: dict[str, object], key: str) -> dict[str, object]:
    """Вложенный объект строки (`provider`, `gateway`) — или отказ по имени.

    Ключ ТРЕБУЕТСЯ, хотя у поля есть значение по умолчанию: писатель строки один
    (`run_record_to_json`), и он кладёт ключ всегда. Пустой словарь на диске
    читается как «прогон не назвал провайдера»; отсутствующий ключ — как
    писатель, который потерял поле, и это разные беды.
    """
    if key not in row:
        raise RunInfoError(f"RunRecord: нет поля {key!r}; в строке {sorted(row)}")
    value = row[key]
    if not isinstance(value, dict):
        raise RunInfoError(f"RunRecord.{key}: ожидался объект, найдено "
                           f"{type(value).__name__} {value!r}")
    return {str(name): inner for name, inner in value.items()}


def run_record_from_json(row: dict[str, object]) -> RunRecord:
    """Обратно. Отказ по имени поля, никогда `row.get(key, "")`: строка,
    записанная сломанным харнессом, должна краснеть при чтении, а не читаться
    как прогон без метки.
    """
    state = _text(row, "state")
    if state not in RUN_STATES:
        raise RunInfoError(f"RunRecord.state: {state!r} не из {RUN_STATES}")
    return RunRecord(
        run_id=_text(row, "run_id"), benchmark=_text(row, "benchmark"),
        started=_text(row, "started"), finished=_text(row, "finished"),
        state=state, tier=_text(row, "tier"), cases=_whole(row, "cases"),
        repeats=_whole(row, "repeats"), triples_done=_whole(row, "triples_done"),
        transport_terminated=_whole(row, "transport_terminated"),
        model=_text(row, "model"), judge_model=_text(row, "judge_model"),
        concurrency=_whole(row, "concurrency"),
        corpus_digest=_text(row, "corpus_digest"), ladder_digest=_text(row, "ladder_digest"),
        label=_text(row, "label"), note=_text(row, "note"),
        ceiling_usd=_amount(row, "ceiling_usd"), spent_usd=_amount(row, "spent_usd"),
        wall_s=_amount(row, "wall_s"), verdict=_text(row, "verdict"),
        worktree=_text(row, "worktree"), run_dir=_text(row, "run_dir"),
        provider=_block(row, "provider"), gateway=_block(row, "gateway"))


def read_runs(path: Path) -> tuple[RunRecord, ...]:
    """Весь реестр. Отсутствующий файл — пустой реестр и НЕ ошибка: первый
    прогон пишется в реестр, которого ещё нет."""
    if not path.exists():
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RunInfoError(f"{path}: ожидался объект, найден {type(raw).__name__}")
    version = raw.get("version")
    if version != RUNS_VERSION:
        raise RunInfoError(f"{path}: version={version!r}, этот код читает {RUNS_VERSION}")
    rows = raw.get("runs")
    if not isinstance(rows, list):
        raise RunInfoError(f"{path}: поле runs должно быть списком, найдено {type(rows).__name__}")
    out: list[RunRecord] = []
    for number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise RunInfoError(f"{path}: строка {number} — не объект")
        out.append(run_record_from_json({str(key): value for key, value in row.items()}))
    return tuple(out)


def append_run(path: Path, record: RunRecord) -> None:
    """Дописать строку. НИКОГДА не переписывает уже записанную.

    Файл переписывается целиком (это JSON-объект, а не jsonl), поэтому
    аддитивность здесь — проверяемое свойство, а не свойство способа записи:
    прежние строки перечитываются и сериализуются обратно теми же байтами, и
    повтор `run_id` — отказ. Альтернатива (jsonl, где аддитивность даётся
    режимом «a») была бы дешевле, но реестр читают руками и глазами, а
    `runs.json` в ТЗ назван именно так.
    """
    before = read_runs(path)
    if any(one.run_id == record.run_id for one in before):
        raise RunInfoError(f"{path}: прогон {record.run_id} уже записан — "
                           f"реестр аддитивен, строка не правится задним числом")
    rows = [run_record_to_json(one) for one in before] + [run_record_to_json(record)]
    path.write_text(json.dumps({"version": RUNS_VERSION, "runs": rows},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def find_run(records: Sequence[RunRecord], run_id: str) -> RunRecord:
    """Прогон по идентификатору или по его началу — руками полный uuid не
    набирают. Неоднозначный префикс — отказ с перечислением, а не первый
    попавшийся."""
    exact = [one for one in records if one.run_id == run_id]
    if exact:
        return exact[0]
    prefixed = [one for one in records if one.run_id.startswith(run_id)]
    if not prefixed:
        raise RunInfoError(f"прогона {run_id!r} в реестре нет")
    if len(prefixed) > 1:
        raise RunInfoError(f"префикс {run_id!r} подходит нескольким: "
                           f"{', '.join(one.run_id for one in prefixed)}")
    return prefixed[0]


def list_lines(records: Sequence[RunRecord]) -> list[str]:
    """`runs list` — одна строка на прогон, новые снизу (реестр аддитивен, и
    порядок чтения совпадает с порядком записи)."""
    if not records:
        return ["реестр пуст"]
    out = ["  прогон       дата              ярус      случаев  цена     вердикт   метка"]
    for one in records:
        mark = "" if one.state == "finished" else " ПРЕРВАН"
        out.append(f"  {one.run_id[:12]} {one.finished[:16]:17} {one.tier:9} "
                   f"{one.cases:7} ${one.spent_usd:7.2f} {one.verdict[:9]:9} "
                   f"{one.label or '—'}{mark}")
    return out


UNKNOWN_BLOCK: str = "не записан"


def provider_line(record: RunRecord) -> str:
    """Провайдер и цены ОДНОЙ строкой для `runs show` (§4.1).

    Читается из строки реестра, а не из `meta.json`: каталог прогона стирают и
    переносят, реестр остаётся. Молчание — «не записан», никогда не «бесплатно»:
    цена, которой нет, и цена, равная нулю, — это два разных прогона.
    """
    if not record.provider:
        return UNKNOWN_BLOCK
    models = record.provider.get("models")
    priced: list[str] = []
    for one in models if isinstance(models, list) else ():
        if not isinstance(one, dict):
            continue
        price = one.get("price")
        rate = (f"${price.get('input_usd_per_mtok')}/${price.get('output_usd_per_mtok')} за MTok"
                if isinstance(price, dict) else "цена неизвестна")
        priced.append(f"{one.get('role')} {one.get('model_id')} ({rate})")
    named = " · ".join(priced) or "моделей нет"
    return f"{record.provider.get('provider', UNKNOWN_BLOCK)} · {named}"


def gateway_line(record: RunRecord) -> str:
    """Чем был шлюз (§4.2). `неизвестно` у полей, о которых никто не спросил —
    сравнение версий образа держится именно на них."""
    if not record.gateway:
        return UNKNOWN_BLOCK
    mode = str(record.gateway.get("mode") or UNKNOWN_BLOCK)
    version = record.gateway.get("engine_version") or "неизвестно"
    digest = record.gateway.get("image_digest") or "неизвестно"
    return f"{mode} · движок {version} · образ {digest}"


def show_lines(record: RunRecord) -> list[str]:
    """`runs show <id>` — всё, что реестр знает об одном прогоне."""
    return [
        f"прогон {record.run_id} · {record.benchmark} · {record.state}",
        f"  начат {record.started} · записан {record.finished} · {record.wall_s:.0f}s",
        f"  ярус {record.tier} · случаев {record.cases} × K={record.repeats} · "
        f"троек завершено {record.triples_done} · параллельно {record.concurrency}",
        f"  агент {record.model} · судья {record.judge_model or '—'}",
        f"  провайдер: {provider_line(record)}",
        f"  шлюз: {gateway_line(record)}",
        f"  корпус {record.corpus_digest[:12] or '—'} · лестница {record.ladder_digest[:12] or '—'}",
        f"  потрачено ${record.spent_usd:.2f} из ${record.ceiling_usd:.2f}",
        f"  снято обрывом провайдера: {record.transport_terminated}",
        f"  вердикт отчёта: {record.verdict}",
        f"  рабочее дерево: {record.worktree or 'неизвестно'}",
        f"  метка: {record.label or '—'}",
        f"  заметка: {record.note or '—'}",
        f"  каталог: {record.run_dir}"]


# --- чего в строке реестра быть не может ----------------------------------------------------

# Опубликованные префиксы ключей и заголовок авторизации — то же правило, что в
# `pseudex/credentials.py`: якорь на ОПУБЛИКОВАННЫЙ префикс, никогда на
# энтропию. «Длинная случайная строка» — это ещё и дайджест корпуса, который в
# строке реестра стоит по делу.
KEY_MARKERS: tuple[str, ...] = (
    "sk-", "sk-ant-", "sk-ps-", "Bearer ", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
    "PSEUDEX_UPSTREAM_KEY", "AKIA", "ghp_", "-----BEGIN")
# Ниже этого значение не ищется в метке: двух-трёх буквенный кусок совпадёт со
# словом («дом», «19»), и запрет перестанет что-либо значить. Тот же довод, что
# у `contracts.PIECE_MIN_CHARS`, но это ДРУГОЕ решение о другом объекте, поэтому
# число своё.
VALUE_MIN_CHARS: int = 4
# Маркер ищется НЕ ПОСЛЕ БУКВЫ ИЛИ ЦИФРЫ, и это не украшение. Голая подстрока
# «sk-» стоит внутри слова «tasks-12», а вычистка применяется теперь и к путям
# (`run_dir` в тексте вердикта) и к имени ветки — то есть к строкам, которые
# такие куски содержат по делу. Ложное срабатывание здесь стирало бы вердикт
# прогона, за который уже заплачено.
_KEY_PATTERN: re.Pattern[str] = re.compile(
    "(?<![0-9A-Za-zА-Яа-яЁё])(" + "|".join(re.escape(one) for one in KEY_MARKERS) + ")")


def key_marker_at(text: str) -> tuple[int, str]:
    """Где в тексте начинается опубликованный префикс ключа и какой это
    префикс; `(-1, "")` — ни одного.

    ОДНА ФУНКЦИЯ НА ДВА ОТВЕТА. `refuse_secrets` отказывает по ней до трат,
    `scrub_free_text` режет по ней после — и если бы каждая искала сама, они
    однажды разошлись бы в том, что считается ключом, а разойдясь, пропустили
    бы его именно на том конце, где отказать уже нельзя.
    """
    match = _KEY_PATTERN.search(text)
    return (-1, "") if match is None else (match.start(), match.group(1))


def refuse_secrets(text: str, field: str) -> None:
    """Отказ, если в тексте виден ключ. Проверка по опубликованным префиксам."""
    at, marker = key_marker_at(text)
    if at >= 0:
        raise RunInfoError(f"{field}: похоже на ключ ({marker!r}) — в реестр не пишем")


def refuse_corpus_values(text: str, field: str, values: frozenset[str]) -> None:
    """Отказ, если в тексте стоит настоящее значение из корпуса.

    Метка пишется человеком по памяти («после правки адреса Иванова»), и это
    единственная дверь, через которую персональные данные попадают в файл,
    который лежит в репозитории вечно. Сравнение регистронезависимое: подмена
    регистра не делает значение другим значением.
    """
    folded = text.casefold()
    found = sorted({value for value in values
                    if len(value) >= VALUE_MIN_CHARS and value.casefold() in folded})
    if found:
        raise RunInfoError(f"{field}: в тексте значение из корпуса ({found[0]!r}) — "
                           f"реестр не хранит значений")


def corpus_values(cases: Sequence[CaseV5]) -> frozenset[str]:
    """Всё, что в выбранных случаях является настоящим значением: поверхность и
    каноническая форма каждого элемента. Части (`parts`) сюда не идут — «дом»
    и «14» не значения, а `refuse_corpus_values` и так отсекает короткое."""
    return frozenset({item.value for case in cases for item in case.base.pii}
                     | {item.canonical for case in cases for item in case.base.pii})


# --- то же самое ПОСЛЕ трат: вычистка вместо отказа -----------------------------------------

# Поля строки реестра, куда приезжает свободный текст. Закрытый список, а не
# «все строки подряд»: `run_id`, дайджесты и даты машинные, и вычистка по ним —
# это шанс испортить идентификатор ради беды, которой там быть не может.
# `verdict` в списке потому, что у прерванного прогона это ТЕКСТ ИСКЛЮЧЕНИЯ, то
# есть всё, что попало в сообщение об ошибке; `worktree` — из-за имени ветки;
# `model` и `judge_model` — потому что их набирает человек флагом.
FREE_TEXT_FIELDS: tuple[str, ...] = (
    "label", "note", "verdict", "worktree", "model", "judge_model")
SCRUBBED_KEY: str = "[вычищен ключ и весь текст после него]"
SCRUBBED_VALUE: str = "[вычищено значение корпуса]"


def scrub_free_text(text: str, values: frozenset[str]) -> tuple[str, tuple[str, ...]]:
    """Тот же текст без ключа и без значений корпуса, и ЧЕМ он отличается.

    ПОЧЕМУ ЗДЕСЬ ВЫЧИСТКА, А НЕ ОТКАЗ. До прогона отказ бесплатен и правилен
    (`refuse_secrets`, `refuse_corpus_values` на `--label`/`--note`). После
    прогона тот же отказ стёр бы строку реестра — то есть прогон, который уже
    потратил деньги, исчез бы из истории, а это ровно то, что §1.2 запрещает.
    Так что текст правится, а не отвергается, и правка ВИДНА в самом тексте:
    молчаливая вычистка — это вердикт, которому нельзя верить.

    ОТ КЛЮЧА РЕЖЕТСЯ ВСЁ ДО КОНЦА СТРОКИ ТЕКСТА. Длина секрета неизвестна, он
    бывает многострочным (PEM), и оставить «хвост на всякий случай» в файле,
    который лежит в репозитории вечно, дороже, чем потерять конец фразы.
    """
    removed: list[str] = []
    at, marker = key_marker_at(text)
    out = text
    if at >= 0:
        out = text[:at] + SCRUBBED_KEY
        removed.append(f"ключ ({marker!r})")
    folded = out.casefold()
    # Длинные вперёд: «Иванов Пётр» и «Иванов» оба в корпусе, и вычистка
    # короткого первой оставила бы от длинного хвост.
    found = sorted({value for value in values
                    if len(value) >= VALUE_MIN_CHARS and value.casefold() in folded},
                   key=len, reverse=True)
    for value in found:
        out = re.sub(re.escape(value), SCRUBBED_VALUE, out, flags=re.IGNORECASE)
    if found:
        # СКОЛЬКО, А НЕ КАКИЕ: причина едет в stderr и в логи прогона, и
        # названное здесь значение было бы той же утечкой другой дорогой.
        removed.append(f"значений корпуса: {len(found)}")
    return out, tuple(removed)


def scrub_record(record: RunRecord, values: frozenset[str]) -> tuple[RunRecord, tuple[str, ...]]:
    """Строка реестра, из которой вычищено всё, чего в ней быть не может, и
    перечень того, что вычищено и из какого поля.

    ОДИН ПРОХОД ПО ЗАКРЫТОМУ СПИСКУ ПОЛЕЙ, а не по тем двум, которые набирает
    человек: `--label` и `--note` были единственными проверяемыми, пока вердикт
    прерванного прогона не начал носить текст произвольного исключения.
    """
    changed: dict[str, str] = {}
    reasons: list[str] = []
    for name in FREE_TEXT_FIELDS:
        cleaned, removed = scrub_free_text(getattr(record, name), values)
        if removed:
            changed[name] = cleaned
            reasons += [f"{name}: {one}" for one in removed]
    return (replace(record, **changed) if changed else record), tuple(reasons)


# --- §1.3 метка ------------------------------------------------------------------------------

# Ярус, ниже которого метка не обязательна. ТЗ: «всё, что не nano». Строка, а
# не множество: ярусов один, и список «дешёвых ярусов» пришлось бы держать
# равным списку в `harness.main`.
FREE_TIER: str = "nano"


def label_required(tier: str) -> bool:
    """Обязательна ли метка для этого яруса. `--ids` — не `nano`: точечный
    прогон стоит денег и через месяц «прогон от 23.09» не значит ничего."""
    return tier != FREE_TIER


# --- §1.1 оценка до запуска ------------------------------------------------------------------

# Кириллица дороже латиницы в токенах: правило «4 знака на токен» английское и
# занизило бы русский корпус примерно в полтора раза. Число названо здесь и
# печатается как оценка, а не как измерение.
CHARS_PER_TOKEN: float = 2.5
# Плечей в тройке — три (C, I, C′). Локальная константа, потому что импорт
# `bench.agentpii4.schema.ARMS` сюда потянул бы v4, а число входит в оценку,
# которая обязана считаться на машине без движка.
ARMS_PER_TRIPLE: int = 3


@dataclass(frozen=True)
class Demand:
    """Чего прогон потребует — из САМОГО корпуса, без единого вызова модели.

    Вилки здесь не про неопределённость цены, а про поведение агента: нижняя
    граница — агент, который сходил в инструмент ровно столько раз, сколько
    объявлено хопами; верхняя — тот же агент плюс повтор на каждую
    подброшенную ошибку (`ForcedError`) и лишний обмен на каждый вызов.
    """

    cases: int              # выбранных случаев
    repeats: int
    triples: int            # cases × repeats
    arms: int               # triples × ARMS_PER_TRIPLE
    model_calls_low: int
    model_calls_high: int
    tool_calls_low: int
    tool_calls_high: int
    prompt_tokens: int


def demand_of(cases: Sequence[CaseV5], repeats: int) -> Demand:
    """Разбор корпуса: ходы пользователя, объявленные вызовы, подброшенные
    ошибки и объём промпта.

    ПРОМПТ РАСТЁТ КВАДРАТИЧНО, и это единственное, что делает оценку токенов
    не бессмысленной: каждый запрос несёт системный промпт и весь разговор до
    себя, поэтому диалог из десяти ходов стоит не десять сообщений, а сумму
    префиксов. Считать длину корпуса и умножать на число вызовов — ошибка в
    разы, и именно так её обычно и считают.

    ЭТО ОЦЕНКА СНИЗУ И НАЗВАНА ТАКОЙ: ответы агента и тела результатов
    инструментов тоже едут в следующий запрос, а их длина известна только
    после прогона. Занижать здесь честнее, чем придумывать коэффициент: вилка
    цены всё равно строится по факту прошлого прогона, а не по токенам.
    """
    turns = 0
    tools = 0
    forced = 0
    chars = 0
    for case in cases:
        # ХОП — ЭТО ОДНО ЗНАЧЕНИЕ, А НЕ ОДИН ВЫЗОВ: результат с тремя значениями
        # объявлен тремя хопами с одним `tool_name` и одним `call_ordinal`
        # (`contracts.Hop`). Считать хопы значило бы насчитать пятнадцать вызовов
        # там, где агент сходит пять раз, — и оценка вызовов разошлась бы с
        # оценкой цены в разы.
        calls_at: dict[int, set[tuple[str, int]]] = {}
        for hop in case.hops:
            if hop.tool_name and hop.call_ordinal >= 0:
                calls_at.setdefault(hop.turn, set()).add((hop.tool_name, hop.call_ordinal))
        tools += sum(len(one) for one in calls_at.values())
        forced += len(case.forced)
        prefix = 0
        for index, message in enumerate(case.base.messages):
            # Системный промпт — не ход, но едет в КАЖДОМ запросе, поэтому он
            # входит в префикс и не входит в счёт ходов.
            prefix += len(message.content)
            if message.role != "user":
                continue
            turns += 1
            # +1 — сам ход, остальное — обмены на вызовы инструментов этого хода.
            chars += prefix * (1 + len(calls_at.get(index, set())))
    triples = len(cases) * repeats
    scale = repeats * ARMS_PER_TRIPLE
    # НИЖНЯЯ ГРАНИЦА ВЫЗОВОВ МОДЕЛИ ВКЛЮЧАЕТ ОБЪЯВЛЕННЫЕ ВЫЗОВЫ ИНСТРУМЕНТОВ:
    # каждый вызов — это ещё один обмен с моделью, и «вызовов модели 189, вызовов
    # инструментов 444» было бы не вилкой, а арифметической невозможностью.
    return Demand(
        cases=len(cases), repeats=repeats, triples=triples,
        arms=triples * ARMS_PER_TRIPLE,
        model_calls_low=(turns + tools) * scale,
        model_calls_high=(turns + tools + forced) * scale,
        tool_calls_low=tools * scale, tool_calls_high=(tools + forced) * scale,
        prompt_tokens=int(chars * scale / CHARS_PER_TOKEN))


# Основания оценки, от лучшего к худшему. Порядок — это и есть выбор: реестр
# спрашивают сверху вниз и берут первое, что нашлось.
BASIS_KINDS: tuple[str, ...] = (
    "same_pair_same_tier",    # та же пара моделей на том же ярусе
    "same_pair_other_tier",   # та же пара, другой ярус, пересчёт на число случаев
    "other_pair_same_tier",   # тот же ярус, другие модели
    "reserve_only")           # прошлых прогонов нет: известен только резерв
# Полуширина интервала по основанию. Это ОБЪЯВЛЕННАЯ полоса, а не измеренная
# дисперсия: измерить её можно будет, когда прогонов одной пары на одном ярусе
# станет больше двух, и тогда это число заменится на перцентиль. Пока широкая
# полоса с честной подписью лучше узкой с придуманной.
SPREAD: dict[str, float] = {
    "same_pair_same_tier": 0.25, "same_pair_other_tier": 0.50,
    "other_pair_same_tier": 0.75, "reserve_only": 1.0}


@dataclass(frozen=True)
class Basis:
    """На чём стоит оценка — и это печатается рядом с числами.

    `per_case_usd` и `per_case_s` — из ЗАВЕРШЁННОГО прогона-основания,
    поделённые на его собственные случаи × повторы. `concurrency` его же:
    время на случай зависит от того, сколько плеч шло параллельно, и без
    этого пересчёта минуты врут ровно во столько раз.
    """

    kind: str                # BASIS_KINDS
    run_id: str
    text: str                # человеческая подпись под оценкой
    per_case_usd: float
    per_case_s: float
    concurrency: int


def _finished(records: Sequence[RunRecord], benchmark: str) -> list[RunRecord]:
    """Завершённые прогоны этого бенчмарка, с измеренной ценой. Прерванный
    прогон основанием быть не может: его цена — цена половины работы."""
    return [one for one in records
            if one.benchmark == benchmark and one.state == "finished"
            and one.spent_usd > 0.0 and one.cases > 0 and one.repeats > 0]


def pick_basis(records: Sequence[RunRecord], benchmark: str, tier: str, model: str,
               judge_model: str) -> Basis:
    """Первое подходящее основание сверху вниз по `BASIS_KINDS`.

    Берётся ПОСЛЕДНИЙ подходящий (реестр аддитивен, значит последний — самый
    свежий), а не самый дешёвый и не средний: среднее по прогонам разных
    версий корпуса — это число, которое не описывает ни один из них.
    """
    finished = _finished(records, benchmark)
    pairs = [one for one in finished if one.model == model and one.judge_model == judge_model]
    ladder: tuple[tuple[str, list[RunRecord]], ...] = (
        ("same_pair_same_tier", [one for one in pairs if one.tier == tier]),
        ("same_pair_other_tier", pairs),
        ("other_pair_same_tier", [one for one in finished if one.tier == tier]))
    for kind, found in ladder:
        if not found:
            continue
        last = found[-1]
        unit = float(last.cases * last.repeats)
        where = {"same_pair_same_tier": f"по последнему прогону {last.tier} той же пары моделей",
                 "same_pair_other_tier": f"пересчётом с яруса {last.tier} той же пары моделей",
                 "other_pair_same_tier": f"по последнему прогону {last.tier} на других моделях "
                                         f"({last.model})"}[kind]
        return Basis(kind=kind, run_id=last.run_id,
                     text=f"{where} ({last.run_id[:12]}, {last.cases}×K={last.repeats}, "
                          f"${last.spent_usd:.2f}, {last.wall_s:.0f}s)",
                     per_case_usd=last.spent_usd / unit, per_case_s=last.wall_s / unit,
                     concurrency=max(1, last.concurrency))
    return Basis(kind="reserve_only", run_id="",
                 text="прошлых прогонов этой пары нет: нижней границы нет, "
                      "верхняя — зарезервированный потолок троек",
                 per_case_usd=0.0, per_case_s=0.0, concurrency=1)


@dataclass(frozen=True)
class Estimate:
    """Что печатает `--dry-run`: вилка по деньгам и времени, спрос по вызовам,
    и основание, на котором всё это стоит."""

    demand: Demand
    basis: Basis
    usd_low: float
    usd_high: float
    usd_point: float
    minutes_low: float
    minutes_high: float
    reserve_usd: float


def estimate(demand: Demand, basis: Basis, reserve_usd: float, concurrency: int) -> Estimate:
    """Вилка из основания и спроса. Ничего не тратит и ничего не пишет.

    `reserve_usd` приходит числом из харнесса (сумма `cap_usd × 3` по выбранным
    случаям): вычислять его здесь значило бы импортировать v4-харнесс, а с ним
    движок — и оценка перестала бы считаться там, где её и хотят посчитать, на
    машине без бандла.
    """
    units = float(demand.triples)
    if basis.kind == "reserve_only":
        # Нижней границы НЕТ. Ноль — не оценка, а признание: печатать «$0.00 —
        # $14.00» честнее, чем придумать середину, которую потом процитируют.
        return Estimate(demand=demand, basis=basis, usd_low=0.0, usd_high=reserve_usd,
                        usd_point=0.0, minutes_low=0.0, minutes_high=0.0,
                        reserve_usd=reserve_usd)
    spread = SPREAD[basis.kind]
    point = basis.per_case_usd * units
    seconds = basis.per_case_s * units * (basis.concurrency / max(1, concurrency))
    return Estimate(demand=demand, basis=basis,
                    usd_low=max(0.0, point * (1.0 - spread)), usd_high=point * (1.0 + spread),
                    usd_point=point,
                    minutes_low=max(0.0, seconds * (1.0 - spread) / 60.0),
                    minutes_high=seconds * (1.0 + spread) / 60.0,
                    reserve_usd=reserve_usd)


def estimate_lines(plan: Estimate) -> list[str]:
    """Оценка словами. Основание — отдельной строкой и всегда: число без него
    читается как измерение."""
    demand = plan.demand
    out = [
        "ОЦЕНКА — ничего не потрачено",
        f"  случаев {demand.cases} × K={demand.repeats} = {demand.triples} троек "
        f"× {ARMS_PER_TRIPLE} плеча = {demand.arms} прогонов агента",
        f"  вызовов модели {demand.model_calls_low}–{demand.model_calls_high} · "
        f"вызовов инструментов {demand.tool_calls_low}–{demand.tool_calls_high}",
        f"  токенов промпта ≈ {demand.prompt_tokens:,}".replace(",", " ")
        + f" (оценка снизу по знакам, {CHARS_PER_TOKEN} знака на токен)"]
    if plan.basis.kind == "reserve_only":
        out.append(f"  цена: неизвестна снизу, не больше ${plan.reserve_usd:.2f} (резерв потолка)")
        out.append("  время: неизвестно — сравнивать не с чем")
    else:
        out.append(f"  цена ${plan.usd_low:.2f}–${plan.usd_high:.2f} "
                   f"(точка ${plan.usd_point:.2f}, резерв потолка ${plan.reserve_usd:.2f})")
        out.append(f"  время {plan.minutes_low:.0f}–{plan.minutes_high:.0f} мин")
    out.append(f"  основание: {plan.basis.text}")
    return out


def actual_lines(plan: Estimate, spent_usd: float, wall_s: float) -> list[str]:
    """«Оценка против факта» в конце прогона — то, ради чего оценка вообще
    записывается: без этой строки никто не узнает, что оценка врёт вдвое."""
    inside = plan.usd_low <= spent_usd <= plan.usd_high
    if plan.basis.kind == "reserve_only":
        verdict = "оценки не было (первый прогон этой пары)"
    else:
        verdict = "в вилке" if inside else "ВНЕ ВИЛКИ"
    return [f"оценка ${plan.usd_low:.2f}–${plan.usd_high:.2f} против факта "
            f"${spent_usd:.2f} — {verdict}",
            f"оценка {plan.minutes_low:.0f}–{plan.minutes_high:.0f} мин против факта "
            f"{wall_s / 60.0:.0f} мин"]


# --- §1.4 обрыв провайдера -------------------------------------------------------------------

# Слово, которым помечен случай, снятый обрывом провайдера. Одна константа на
# три читателя: причина в строке тройки, счётчик в реестре и строка в отчёте.
TRANSPORT_TERMINATED: str = "terminated: transport"
RETRY_ATTEMPTS: int = 3
RETRY_BASE_S: float = 2.0
RETRY_MAX_S: float = 30.0
# Ошибки транспорта ПО ИМЕНИ КЛАССА, а не по импорту: классы ошибок живут в SDK
# провайдера, и модуль, который их импортирует, нельзя ни прочитать, ни
# протестировать на машине без SDK. Таблица закрытая — «всё, что не наше»
# ошибкой транспорта не считается, иначе повтор будет прятать наши же дефекты.
TRANSPORT_ERROR_NAMES: frozenset[str] = frozenset({
    "APIConnectionError", "APITimeoutError", "APIStatusError", "InternalServerError",
    "OverloadedError", "RateLimitError", "ServiceUnavailableError",
    "CLIConnectionError", "CLIJSONDecodeError", "ProcessError",
    "ClientConnectorError", "ServerDisconnectedError", "IncompleteRead"})
# Встроенные классы — отдельно: `ConnectionError` и `TimeoutError` не имеют
# отношения к SDK и ловятся по типу, как и положено.
TRANSPORT_ERROR_TYPES: tuple[type[BaseException], ...] = (ConnectionError, TimeoutError)


def is_transport_error(error: BaseException) -> bool:
    """Обрыв провайдера — или наш дефект.

    `OSError` целиком сюда НЕ входит: «нет места на диске» и «файла нет» — это
    мы, и повторять их с отступом значит три раза подождать перед тем же
    отказом. Из OSError берётся только `ConnectionError`.
    """
    return (isinstance(error, TRANSPORT_ERROR_TYPES)
            or type(error).__name__ in TRANSPORT_ERROR_NAMES)


def is_transient_error(error: BaseException) -> bool:
    """Флаки-отказ, который §1.4 повторяет: транспорт плюс три класса живых флаков.

    Транспорт (`is_transport_error`) уже покрывает сетевые обрывы SDK. Сюда
    добавлены классы, которые ИНАЧЕ молча снимали тройку как excluded, хотя их
    исход зависит от ОТВЕТА провайдера, а не от нашего кода — повтор даёт другой
    сэмпл и потому оправдан:
    - `ConnectorError` — DeepSeek оборвал ответ (`response ended incomplete`);
    - `ConnectorLimit` — его подкласс, лимит вызовов инструментов (следующий
      сэмпл делает меньше вызовов);
    - `WriterError` — слот не round-trip'нулся как JSON-строка (значение,
      написанное моделью, сломало escaping; другой сэмпл пишет другое).

    Наши ДЕТЕРМИНИРОВАННЫЕ дефекты сюда НЕ входят: `ValueError` маскирования,
    `KeyError`, `FileNotFoundError` повторять значит трижды подождать перед тем
    же отказом и спрятать причину за словом «флаки».
    """
    return (is_transport_error(error)
            or isinstance(error, ConnectorError)
            or isinstance(error, WriterError))


def backoff_seconds(attempt: int, jitter: float, base_s: float = RETRY_BASE_S) -> float:
    """Сколько ждать перед попыткой `attempt` (1-based), с джиттером.

    `base_s` — первый отступ (флаг `--retry-delay`): задержка растёт
    экспоненциально (`base_s * 2^(attempt-1)`) и упирается в `RETRY_MAX_S`.
    Джиттер приходит ЧИСЛОМ 0..1 от вызывающего, а не берётся здесь из
    `random`: функция с собственным источником случайности не проверяется —
    тест может утверждать про неё только неравенство. Джиттер полный
    (`0..delay`), а не «±10%»: половина клиентов, повторяющих через ровно 4
    секунды, — это тот же всплеск, только через 4 секунды.
    """
    if attempt < 1:
        raise RunInfoError(f"backoff_seconds: попытка {attempt} — нумерация с 1")
    if not 0.0 <= jitter <= 1.0:
        raise RunInfoError(f"backoff_seconds: джиттер {jitter} вне 0..1")
    if base_s < 0:
        raise RunInfoError(f"backoff_seconds: отступ {base_s} отрицателен")
    delay = min(RETRY_MAX_S, base_s * (2 ** (attempt - 1)))
    return delay * jitter


# --- §7.1 стоп-кран по цене на случай --------------------------------------------------------

# Во сколько раз средняя цена случая должна превысить ожидаемую, чтобы прогон
# остановился. ТЗ: «больше чем вдвое».
COST_BRAKE_FACTOR: float = 2.0
# Меньше этого числа случаев среднее — это один выброс. Кран, срабатывающий на
# первом дорогом случае, убьёт прогон, в котором корпус просто отсортирован по
# цене вниз (а `drive_v5` сортирует его именно так).
BRAKE_MIN_CASES: int = 3


def brake_verdict(done: int, spent_usd: float, expected_per_case_usd: float,
                  last_case: str) -> str:
    """Пустая строка — идём дальше; иначе текст отказа с числами.

    Чистая функция, а не объект со счётчиками: состояние прогона и так живёт в
    `drive_v5`, а второй его экземпляр — это второе место, где «сколько мы уже
    потратили» может разойтись с журналом.
    """
    if done < BRAKE_MIN_CASES or expected_per_case_usd <= 0.0:
        return ""
    average = spent_usd / done
    limit = expected_per_case_usd * COST_BRAKE_FACTOR
    if average <= limit:
        return ""
    return (f"СТОП ПО ЦЕНЕ: средняя цена случая ${average:.4f} превысила ожидаемую "
            f"${expected_per_case_usd:.4f} более чем в {COST_BRAKE_FACTOR:g} раза "
            f"(порог ${limit:.4f}); {done} троек на ${spent_usd:.2f}, последняя — {last_case}")


# --- вердикт отчёта для строки реестра -------------------------------------------------------

def verdict_of(run_dir: Path, run_id: str) -> str:
    """«полный» или «НЕПОЛНЫЙ: …» — по ФАЙЛАМ прогона, не по тексту отчёта.

    `<run>.gate.json` и штамп калибровки — то, на чём отчёт сам основывает
    метку `INCOMPLETE_REPORT_MARK`; читать её грепом по markdown значило бы
    завести второе определение полноты, которое разойдётся с первым при первой
    же правке формулировки.
    """
    gate_path = r.run_file(run_dir, run_id, "<run>.gate.json")
    if not gate_path.exists():
        return f"{INCOMPLETE_REPORT_MARK}: нет {gate_path.name} — отчёт не доказал, что печатал"
    raw = json.loads(gate_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RunInfoError(f"{gate_path}: ожидался объект, найден {type(raw).__name__}")
    refused = sorted(name for name, verdict in raw.items()
                     if not (isinstance(verdict, dict) and verdict.get("printable") is True))
    reasons: list[str] = []
    if refused:
        reasons.append("не печатаются: " + ", ".join(refused))
    judge_path = r.run_file(run_dir, run_id, "<run>.judge.jsonl")
    if judge_path.exists():
        rows = r.read_rows(judge_path)
        if rows and "calibrated" in rows[0] and not r.calibration_stamp_from_json(rows[0]).calibrated:
            reasons.append("судья не откалиброван")
    if not reasons:
        return "полный"
    return f"{INCOMPLETE_REPORT_MARK}: " + "; ".join(reasons)


def utc_now() -> str:
    """Одно написание времени на весь модуль и на харнесс."""
    return datetime.now(timezone.utc).isoformat()


# --- CLI --------------------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("list", "show"))
    parser.add_argument("run_id", nargs="?", default="")
    parser.add_argument("--runs", default=str(RUNS_PATH))
    args = parser.parse_args()
    records = read_runs(Path(args.runs))
    if args.command == "list":
        for line in list_lines(records):
            print(line)
        return 0
    if not args.run_id:
        print("show требует идентификатор прогона", file=sys.stderr)
        return 2
    try:
        record = find_run(records, args.run_id)
    except RunInfoError as refused:
        print(str(refused), file=sys.stderr)
        return 2
    for line in show_lines(record):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
