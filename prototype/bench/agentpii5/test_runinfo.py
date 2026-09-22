"""Прогон как объект, закреплённый ОФФЛАЙН: реестр, оценка, повтор, стоп-кран.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_runinfo

Ни одной модели, ни одного ключа, ни одного доллара: всё, что здесь
проверяется, обязано работать на файлах законченного прогона — иначе
`--dry-run`, `runs list` и `runs show` нельзя будет выполнить на чужой машине,
ради чего они и заводились (ТЗ §8).

ЧТО ЗДЕСЬ ДОКАЗЫВАЕТСЯ, А НЕ ОБЪЯВЛЯЕТСЯ.
* реестр аддитивен: повтор `run_id` — отказ, прежние строки переживают запись
  новой БАЙТ В БАЙТ (сравниваются сериализации, а не длина списка);
* ни ключ, ни настоящее значение из корпуса не проходят в строку — и короткий
  кусок («дом») не выдаёт ложного отказа, иначе запрет отключат через неделю;
* оценка НАЗЫВАЕТ основание и меняет его, когда меняются данные реестра;
  пустой реестр даёт «нижней границы нет», а не придуманную середину;
* отступ растёт, упирается в потолок и полностью зажиттерен;
* стоп-кран не срабатывает ни ниже пола по числу случаев, ни без оценки.
"""
import json
import sys
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from bench.agentpii5 import records
from bench.agentpii5 import runinfo
from bench.agentpii5.contracts import (
    INCOMPLETE_REPORT_MARK, CalibrationStamp, ForcedError)
from bench.agentpii5.fixtures import NAME_ITEM, PHONE_ITEM, _case, _hop

RUN_ID: str = "11111111-2222-3333-4444-555555555555"
OTHER_ID: str = "99999999-8888-7777-6666-555555555555"


def _record(run_id: str, tier: str, model: str, judge: str, cases: int,
            spent: float, wall_s: float) -> runinfo.RunRecord:
    return runinfo.RunRecord(
        run_id=run_id, benchmark="agentpii5", started="2026-09-23T10:00:00+00:00",
        finished="2026-09-23T11:00:00+00:00", state="finished", tier=tier, cases=cases,
        repeats=1, triples_done=cases, transport_terminated=0, model=model,
        judge_model=judge, concurrency=2, corpus_digest="d" * 64, ladder_digest="l" * 64,
        label="после правки адресов", note="", ceiling_usd=12.0, spent_usd=spent,
        wall_s=wall_s, verdict="полный", worktree="", run_dir="bench/runs/2026-09-23/x")


def _two_turn_case(case_id: str, tools: int) -> object:
    """Случай из двух ходов пользователя, с `tools` вызовами во втором ходе."""
    hops = tuple(_hop("OUT", "tool_arg", "p1", index, 1, "crm_find_contact", index, -1, "name")
                 for index in range(tools))
    return _case(case_id, "single", ("Здравствуйте, я Пахомов", "перезвоните на мой номер"),
                 (NAME_ITEM, PHONE_ITEM), hops)


# --- §1.2 реестр ------------------------------------------------------------------------------

def test_the_registry_is_additive() -> list[str]:
    """Строка не правится задним числом, и прежние строки переживают запись."""
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "runs.json"
        if runinfo.read_runs(path) != ():
            failures.append("несуществующий реестр прочитался не как пустой")
        first = _record(RUN_ID, "nano", "haiku", "sonnet", 12, 1.20, 600.0)
        runinfo.append_run(path, first)
        runinfo.append_run(path, _record(OTHER_ID, "medium", "haiku", "sonnet", 120, 14.0, 3600.0))
        rows = runinfo.read_runs(path)
        if len(rows) != 2:
            failures.append(f"в реестре {len(rows)} строк, ожидались две")
        elif runinfo.run_record_to_json(rows[0]) != runinfo.run_record_to_json(first):
            failures.append("первая строка изменилась при дописывании второй")
        try:
            runinfo.append_run(path, replace(first, label="другая метка"))
            failures.append("повтор run_id записан — реестр перестал быть аддитивным")
        except runinfo.RunInfoError:
            pass
        # НЕГАТИВ: реестр с чужой версией не читается как пустой.
        alien = Path(tmp) / "alien.json"
        alien.write_text(json.dumps({"version": 99, "runs": []}), encoding="utf-8")
        try:
            runinfo.read_runs(alien)
            failures.append("реестр чужой версии прочитан молча")
        except runinfo.RunInfoError:
            pass
    return failures


def test_a_row_refuses_a_missing_field() -> list[str]:
    """Отказ по ИМЕНИ поля: строка сломанного писателя должна краснеть, а не
    читаться как прогон без метки."""
    failures: list[str] = []
    row = runinfo.run_record_to_json(_record(RUN_ID, "nano", "haiku", "sonnet", 3, 0.3, 30.0))
    if runinfo.run_record_from_json(dict(row)) != _record(RUN_ID, "nano", "haiku", "sonnet",
                                                          3, 0.3, 30.0):
        failures.append("строка не пережила круг to_json → from_json")
    for field in ("label", "spent_usd", "transport_terminated", "verdict"):
        broken = {key: value for key, value in row.items() if key != field}
        try:
            runinfo.run_record_from_json(broken)
            failures.append(f"строка без поля {field} прочиталась")
        except runinfo.RunInfoError as refused:
            if field not in str(refused):
                failures.append(f"отказ про {field} не называет поле: {refused}")
    # НЕГАТИВ: «12» строкой вместо числа — тоже отказ, а не молчаливый ноль.
    typed = dict(row)
    typed["cases"] = "12"
    try:
        runinfo.run_record_from_json(typed)
        failures.append("число случаев строкой прочиталось как число")
    except runinfo.RunInfoError:
        pass
    return failures


def test_neither_a_key_nor_a_corpus_value_reaches_the_registry() -> list[str]:
    """Метка — единственная дверь в файл, который лежит в репозитории вечно."""
    failures: list[str] = []
    values = runinfo.corpus_values([_two_turn_case("c-0001", 1)])   # type: ignore[list-item]
    for text in (f"перевыпустил ключ sk-ant-api03-{'z' * 20}", "Authorization: Bearer abc"):
        try:
            runinfo.refuse_secrets(text, "--label")
            failures.append(f"ключ прошёл в реестр: {text[:24]}")
        except runinfo.RunInfoError:
            pass
    try:
        runinfo.refuse_corpus_values(f"после правки {NAME_ITEM.value}", "--label", values)
        failures.append("настоящее значение из корпуса прошло в реестр")
    except runinfo.RunInfoError as refused:
        if "корпус" not in str(refused):
            failures.append(f"отказ не объясняет причину: {refused}")
    # ПОЛОЖИТЕЛЬНЫЙ КОНТРОЛЬ: обычная метка проходит, иначе запрет отключат.
    for text in ("после правки адресов", "проверка стоп-крана", ""):
        runinfo.refuse_secrets(text, "--label")
        runinfo.refuse_corpus_values(text, "--label", values)
    # И регистр значения не спасает.
    try:
        runinfo.refuse_corpus_values(NAME_ITEM.value.upper(), "--label", values)
        failures.append("значение в другом регистре прошло")
    except runinfo.RunInfoError:
        pass
    # КОРОТКОЕ НЕ ЛОВИТСЯ: иначе «дом» в метке даст ложный отказ.
    short = frozenset({"дом", "19"})
    runinfo.refuse_corpus_values("дом 19 переехал", "--label", short)
    return failures


def test_list_and_show_name_what_the_registry_knows() -> list[str]:
    failures: list[str] = []
    records_ = (_record(RUN_ID, "nano", "haiku", "sonnet", 12, 1.2, 600.0),
                replace(_record(OTHER_ID, "medium", "haiku", "sonnet", 120, 14.0, 3600.0),
                        state="interrupted", transport_terminated=4))
    listed = "\n".join(runinfo.list_lines(records_))
    for wanted in (RUN_ID[:12], OTHER_ID[:12], "после правки адресов", "ПРЕРВАН"):
        if wanted not in listed:
            failures.append(f"runs list не назвал {wanted!r}")
    shown = "\n".join(runinfo.show_lines(records_[1]))
    for wanted in ("снято обрывом провайдера: 4", "medium", "interrupted"):
        if wanted not in shown:
            failures.append(f"runs show не назвал {wanted!r}")
    if "реестр пуст" not in runinfo.list_lines(()):
        failures.append("пустой реестр напечатал таблицу без строк вместо слов")
    found = runinfo.find_run(records_, RUN_ID[:8])
    if found.run_id != RUN_ID:
        failures.append("прогон не находится по префиксу")
    # НЕГАТИВ: неоднозначный префикс — отказ, а не первый попавшийся.
    try:
        runinfo.find_run((records_[0], replace(records_[0], run_id=RUN_ID[:8] + "x" * 28)),
                         RUN_ID[:8])
        failures.append("неоднозначный префикс вернул прогон")
    except runinfo.RunInfoError:
        pass
    return failures


# --- §1.1 оценка -------------------------------------------------------------------------------

def test_the_estimate_names_its_basis() -> list[str]:
    """Число без основания читается как измерение; основание — часть оценки."""
    failures: list[str] = []
    empty = runinfo.pick_basis((), "agentpii5", "medium", "haiku", "sonnet")
    if empty.kind != "reserve_only":
        failures.append(f"пустой реестр дал основание {empty.kind}")
    plan = runinfo.estimate(runinfo.demand_of([_two_turn_case("c-1", 1)], 1),  # type: ignore[list-item]
                            empty, 9.0, 2)
    if plan.usd_low != 0.0 or plan.usd_high != 9.0:
        failures.append(f"без прошлых прогонов вилка {plan.usd_low}–{plan.usd_high}, "
                        f"ожидались 0 и резерв")
    text = "\n".join(runinfo.estimate_lines(plan))
    if "нижней границы нет" not in text:
        failures.append("оценка без основания не сказала, что нижней границы нет")
    if "основание:" not in text:
        failures.append("оценка не назвала основание")

    same = (_record(RUN_ID, "medium", "haiku", "sonnet", 100, 10.0, 6000.0),)
    basis = runinfo.pick_basis(same, "agentpii5", "medium", "haiku", "sonnet")
    if basis.kind != "same_pair_same_tier":
        failures.append(f"прогон той же пары на том же ярусе дал {basis.kind}")
    if abs(basis.per_case_usd - 0.10) > 1e-9:
        failures.append(f"цена на случай {basis.per_case_usd}, ожидалась 0.10")
    if RUN_ID[:12] not in basis.text:
        failures.append("подпись основания не называет прогон, на котором стоит")

    other_tier = runinfo.pick_basis(same, "agentpii5", "nano", "haiku", "sonnet")
    if other_tier.kind != "same_pair_other_tier":
        failures.append(f"другой ярус той же пары дал {other_tier.kind}")
    other_pair = runinfo.pick_basis(same, "agentpii5", "medium", "opus", "sonnet")
    if other_pair.kind != "other_pair_same_tier":
        failures.append(f"другие модели на том же ярусе дали {other_pair.kind}")
    # НЕГАТИВ: прерванный прогон основанием быть не может — его цена это цена
    # половины работы.
    stopped = (replace(same[0], state="interrupted"),)
    if runinfo.pick_basis(stopped, "agentpii5", "medium", "haiku", "sonnet").kind != "reserve_only":
        failures.append("прерванный прогон стал основанием оценки")
    # И чужой бенчмарк тоже.
    alien = (replace(same[0], benchmark="agentpii4"),)
    if runinfo.pick_basis(alien, "agentpii5", "medium", "haiku", "sonnet").kind != "reserve_only":
        failures.append("прогон другого бенчмарка стал основанием оценки")
    return failures


def test_the_estimate_scales_with_the_selection() -> list[str]:
    """40 случаев по основанию из 100 стоят 0.4 от него — и вилка накрывает точку."""
    failures: list[str] = []
    basis = runinfo.pick_basis((_record(RUN_ID, "medium", "haiku", "sonnet", 100, 10.0, 6000.0),),
                               "agentpii5", "medium", "haiku", "sonnet")
    cases = [_two_turn_case(f"c-{index}", 1) for index in range(40)]
    plan = runinfo.estimate(runinfo.demand_of(cases, 1), basis, 99.0, 2)   # type: ignore[arg-type]
    if abs(plan.usd_point - 4.0) > 1e-6:
        failures.append(f"точка оценки ${plan.usd_point}, ожидалась $4.00")
    if not plan.usd_low < plan.usd_point < plan.usd_high:
        failures.append(f"вилка {plan.usd_low}–{plan.usd_high} не накрывает точку")
    # ВРЕМЯ ПЕРЕСЧИТЫВАЕТСЯ ПО ПАРАЛЛЕЛИЗМУ: основание шло в 2 потока.
    faster = runinfo.estimate(runinfo.demand_of(cases, 1), basis, 99.0, 4)  # type: ignore[arg-type]
    if not faster.minutes_high < plan.minutes_high:
        failures.append(f"вдвое больший параллелизм не сократил оценку времени: "
                        f"{faster.minutes_high} против {plan.minutes_high}")
    # И повторы умножают тройки.
    twice = runinfo.estimate(runinfo.demand_of(cases, 2), basis, 99.0, 2)   # type: ignore[arg-type]
    if abs(twice.usd_point - 2 * plan.usd_point) > 1e-6:
        failures.append(f"K=2 не удвоил оценку: {twice.usd_point} против {plan.usd_point}")
    return failures


def test_the_demand_counts_turns_tools_and_a_growing_prompt() -> list[str]:
    """Спрос читается из корпуса: ходы, объявленные вызовы, подброшенные ошибки
    и КВАДРАТИЧНО растущий промпт."""
    failures: list[str] = []
    bare = runinfo.demand_of([_two_turn_case("c-1", 0)], 1)      # type: ignore[list-item]
    withtool = runinfo.demand_of([_two_turn_case("c-1", 1)], 1)  # type: ignore[list-item]
    if bare.model_calls_low != 2 * runinfo.ARMS_PER_TRIPLE:
        failures.append(f"нижняя оценка вызовов {bare.model_calls_low}, ожидались два хода × плечи")
    if bare.model_calls_high != bare.model_calls_low:
        failures.append("случай без инструментов получил верхнюю оценку выше нижней")
    if withtool.tool_calls_low != runinfo.ARMS_PER_TRIPLE:
        failures.append(f"объявленный вызов не посчитан: {withtool.tool_calls_low}")
    if withtool.model_calls_low < withtool.tool_calls_low:
        failures.append(f"вызовов модели ({withtool.model_calls_low}) меньше, чем вызовов "
                        f"инструментов ({withtool.tool_calls_low}) — арифметически невозможно")
    # ТРИ ЗНАЧЕНИЯ В ОДНОМ РЕЗУЛЬТАТЕ — ЭТО ОДИН ВЫЗОВ: хоп несёт одно значение,
    # и счёт по хопам насчитал бы три.
    one_call = _case("c-4", "single", ("а", "б"), (NAME_ITEM, PHONE_ITEM), tuple(
        _hop("IN", "tool", f"p{index}", index, 1, "crm_find_contact", 0, -1, "name")
        for index in (1, 2)))
    if runinfo.demand_of([one_call], 1).tool_calls_low != runinfo.ARMS_PER_TRIPLE:
        failures.append("два значения одного результата посчитаны как два вызова")
    if withtool.prompt_tokens <= bare.prompt_tokens:
        failures.append("вызов инструмента не добавил ни одного токена промпта")
    forced = runinfo.demand_of(                                   # type: ignore[list-item]
        [replace(_two_turn_case("c-1", 1),                         # type: ignore[arg-type]
                 forced=(ForcedError(tool_name="crm_find_contact", call_ordinal=0,
                                     code="bad_value", echo_item_id="p1",
                                     message_template="{value}"),))], 1)
    if forced.model_calls_high <= withtool.model_calls_high:
        failures.append("подброшенная ошибка не подняла верхнюю оценку вызовов")
    # КВАДРАТИЧНОСТЬ: второй ход стоит дороже первого, потому что несёт первый.
    one_turn = runinfo.demand_of([_case("c-2", "single", ("а" * 100,),   # type: ignore[list-item]
                                        (NAME_ITEM,), ())], 1)
    two_turns = runinfo.demand_of([_case("c-3", "single", ("а" * 100, "а" * 100),
                                         (NAME_ITEM,), ())], 1)          # type: ignore[list-item]
    if two_turns.prompt_tokens < 3 * one_turn.prompt_tokens:
        failures.append(f"промпт посчитан линейно: {two_turns.prompt_tokens} против "
                        f"{one_turn.prompt_tokens} — второй ход должен нести первый")
    return failures


def test_the_estimate_is_compared_with_the_fact() -> list[str]:
    """«Оценка против факта» — то, ради чего оценка записывается."""
    failures: list[str] = []
    basis = runinfo.pick_basis((_record(RUN_ID, "medium", "haiku", "sonnet", 100, 10.0, 6000.0),),
                               "agentpii5", "medium", "haiku", "sonnet")
    plan = runinfo.estimate(runinfo.demand_of([_two_turn_case(f"c-{i}", 1) for i in range(100)],
                                              1), basis, 99.0, 2)   # type: ignore[arg-type]
    inside = "\n".join(runinfo.actual_lines(plan, 9.5, 5400.0))
    if "в вилке" not in inside:
        failures.append(f"факт внутри вилки назван иначе: {inside}")
    outside = "\n".join(runinfo.actual_lines(plan, 40.0, 5400.0))
    if "ВНЕ ВИЛКИ" not in outside:
        failures.append(f"факт вчетверо выше вилки не назван выходом за неё: {outside}")
    return failures


# --- §1.3 метка --------------------------------------------------------------------------------

def test_the_label_is_required_above_nano() -> list[str]:
    failures: list[str] = []
    if runinfo.label_required("nano"):
        failures.append("метку требуют и от nano — тогда её будут писать наугад")
    for tier in ("small", "medium", "large", "holdout", "max", "ids"):
        if not runinfo.label_required(tier):
            failures.append(f"ярус {tier} не требует метки")
    return failures


# --- §1.4 обрыв провайдера ---------------------------------------------------------------------

def test_the_backoff_grows_and_is_fully_jittered() -> list[str]:
    failures: list[str] = []
    full = [runinfo.backoff_seconds(attempt, 1.0) for attempt in range(1, 7)]
    # СТРОГО растёт до потолка: `sorted(full) == full` зеленеет и на плоском
    # списке, то есть на повторе без отступа — ровно на том, что здесь нельзя.
    if not all(left < right for left, right in zip(full[:4], full[1:5])):
        failures.append(f"отступ не растёт: {full}")
    if full[-1] != runinfo.RETRY_MAX_S:
        failures.append(f"отступ не упирается в потолок: {full[-1]} против {runinfo.RETRY_MAX_S}")
    if runinfo.backoff_seconds(3, 0.0) != 0.0:
        failures.append("джиттер не полный: при 0 отступ должен быть нулевым")
    if not 0.0 < runinfo.backoff_seconds(3, 0.5) < full[2]:
        failures.append("джиттер 0.5 не даёт половину отступа")
    for attempt, jitter in ((0, 0.5), (1, 1.5), (1, -0.1)):
        try:
            runinfo.backoff_seconds(attempt, jitter)
            failures.append(f"backoff_seconds({attempt}, {jitter}) не отказал")
        except runinfo.RunInfoError:
            pass
    return failures


def test_only_a_named_transport_error_is_retried() -> list[str]:
    """Таблица закрытая: «всё, что не наше» повторять нельзя — повтор спрячет
    наш же дефект за словом «транспорт»."""
    failures: list[str] = []

    class OverloadedError(RuntimeError):
        """Имя как у ошибки SDK — ловится по имени класса."""

    class ValueMissing(RuntimeError):
        """Наш дефект: имя не в таблице."""

    if not runinfo.is_transport_error(ConnectionError("сброс")):
        failures.append("ConnectionError не признан обрывом транспорта")
    if not runinfo.is_transport_error(OverloadedError("529")):
        failures.append("OverloadedError не признан обрывом транспорта")
    for error in (ValueError("плохое значение"), KeyError("p1"), ValueMissing("нет поля"),
                  FileNotFoundError("нет файла")):
        if runinfo.is_transport_error(error):
            failures.append(f"{type(error).__name__} признан обрывом транспорта — "
                            f"наш дефект будет повторён трижды и назван чужим")
    return failures


# --- §7.1 стоп-кран ----------------------------------------------------------------------------

def test_the_brake_fires_only_past_the_floor_and_the_factor() -> list[str]:
    failures: list[str] = []
    below = runinfo.brake_verdict(runinfo.BRAKE_MIN_CASES - 1, 100.0, 0.01, "c-1")
    if below:
        failures.append(f"кран сработал на {runinfo.BRAKE_MIN_CASES - 1} случаях — "
                        f"один выброс убил бы прогон")
    inside = runinfo.brake_verdict(10, 10 * 0.15, 0.10, "c-1")
    if inside:
        failures.append(f"кран сработал в полтора раза: {inside}")
    past = runinfo.brake_verdict(10, 10 * 0.25, 0.10, "c-7|1")
    if not past:
        failures.append("кран не сработал при превышении вдвое с половиной")
    elif "c-7|1" not in past or "0.10" not in past:
        failures.append(f"отказ не называет случай и числа: {past}")
    # НЕ ВООРУЖЁН БЕЗ ОЦЕНКИ: первый прогон новой пары моделей не должен
    # умирать оттого, что сравнивать не с чем.
    if runinfo.brake_verdict(50, 500.0, 0.0, "c-1"):
        failures.append("кран сработал без оценки")
    return failures


# --- вердикт отчёта ----------------------------------------------------------------------------

def _stamp(calibrated: bool) -> dict[str, object]:
    return records.calibration_stamp_to_json(CalibrationStamp(
        judge_model="claude-sonnet-5", prompt_sha256="a" * 64, n=300, raw_agreement=0.9,
        kappa=0.8, per_type_kappa={}, repeat_disagreement=0.01, calibrated=calibrated))


def _run_dir(root: Path, gate: dict[str, object], calibrated: bool) -> Path:
    run_dir = root / "run"
    run_dir.mkdir(parents=True)
    records.run_file(run_dir, RUN_ID, "<run>.gate.json").write_text(
        json.dumps(gate, ensure_ascii=False), encoding="utf-8")
    records.append_row(records.run_file(run_dir, RUN_ID, "<run>.judge.jsonl"), _stamp(calibrated))
    return run_dir


def test_the_verdict_is_read_from_the_run_files() -> list[str]:
    """Полнота берётся из `<run>.gate.json` и штампа, а не грепом по отчёту:
    второе определение полноты разойдётся с первым на первой же правке слов."""
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        full = _run_dir(Path(tmp) / "a", {"leak": {"printable": True, "why": ""}}, True)
        if runinfo.verdict_of(full, RUN_ID) != "полный":
            failures.append(f"полный отчёт назван иначе: {runinfo.verdict_of(full, RUN_ID)}")
        refused = _run_dir(Path(tmp) / "b",
                           {"leak": {"printable": True, "why": ""},
                            "form_hOUT": {"printable": False, "why": "нет наблюдений"}}, True)
        verdict = runinfo.verdict_of(refused, RUN_ID)
        if INCOMPLETE_REPORT_MARK not in verdict or "form_hOUT" not in verdict:
            failures.append(f"отказ гейта не попал в вердикт: {verdict}")
        uncalibrated = _run_dir(Path(tmp) / "c", {"leak": {"printable": True, "why": ""}}, False)
        if "судья не откалиброван" not in runinfo.verdict_of(uncalibrated, RUN_ID):
            failures.append("некалиброванный судья не сделал вердикт неполным")
        bare = Path(tmp) / "d"
        bare.mkdir()
        if INCOMPLETE_REPORT_MARK not in runinfo.verdict_of(bare, RUN_ID):
            failures.append("прогон без gate.json назван полным")
    return failures


def test_runinfo_never_imports_the_engine() -> list[str]:
    """Оценку и реестр считают там, где движка нет: на чужой машине, в CI, на
    копии каталога прогона."""
    bad = [name for name in sys.modules if name.split(".")[0] == "pseudex"]
    return [f"движок импортирован: {sorted(bad)[:3]}"] if bad else []


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("the_registry_is_additive", test_the_registry_is_additive),
        ("a_row_refuses_a_missing_field", test_a_row_refuses_a_missing_field),
        ("neither_a_key_nor_a_corpus_value_reaches_the_registry",
         test_neither_a_key_nor_a_corpus_value_reaches_the_registry),
        ("list_and_show_name_what_the_registry_knows",
         test_list_and_show_name_what_the_registry_knows),
        ("the_estimate_names_its_basis", test_the_estimate_names_its_basis),
        ("the_estimate_scales_with_the_selection", test_the_estimate_scales_with_the_selection),
        ("the_demand_counts_turns_tools_and_a_growing_prompt",
         test_the_demand_counts_turns_tools_and_a_growing_prompt),
        ("the_estimate_is_compared_with_the_fact", test_the_estimate_is_compared_with_the_fact),
        ("the_label_is_required_above_nano", test_the_label_is_required_above_nano),
        ("the_backoff_grows_and_is_fully_jittered", test_the_backoff_grows_and_is_fully_jittered),
        ("only_a_named_transport_error_is_retried", test_only_a_named_transport_error_is_retried),
        ("the_brake_fires_only_past_the_floor_and_the_factor",
         test_the_brake_fires_only_past_the_floor_and_the_factor),
        ("the_verdict_is_read_from_the_run_files", test_the_verdict_is_read_from_the_run_files),
        ("runinfo_never_imports_the_engine", test_runinfo_never_imports_the_engine),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("runinfo: PASS" if not failures else "runinfo: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
