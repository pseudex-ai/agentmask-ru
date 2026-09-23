"""`calibration.py` pinned: the strata, the thresholds, κ on a textbook table.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_calibration

Offline, no model. The thresholds are checked from BOTH sides — a sample that
must calibrate and a sample that must not — because a `calibrated` that is
True on everything is a certificate, and the spec's whole point is that an
uncalibrated judge stops a report.
"""
import asyncio
import json
import sys
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from bench.agentpii4.records import ArmMeta
from bench.agentpii5 import calibration as c
from bench.agentpii5 import judge
from bench.agentpii5 import records as r
from bench.agentpii5 import report
from bench.agentpii5.contracts import (
    CALIBRATION, JUDGE_LABELS, ArmRunV5, CalibrationRecord, CalibrationStamp, CaseV5,
    HopObservation, JudgeInput, JudgeVerdict, MentionRecord, RunObservation, ToolResultRecord)
from bench.agentpii5.fixtures import (
    NAME_ITEM, PHONE_ITEM, _case, _hop, _run, _with_replies, _with_subs)
from bench.agentpii5.form import form_match
from bench.agentpii5.schema import case_v5_to_json

MODEL: str = "claude-sonnet-5"
PROMPT: str = "a" * 64
RUN_ID: str = "abc123"
SUBSTITUTE: str = "Пахомова Ольга"
# Three cases, so a sample can leave one out and the difference is visible.
ANSWER_IDS: tuple[str, ...] = ("ans-0001", "ans-0002", "ans-0003")


def _observation(case_id: str, repeat: int, behaviour: str, register: str,
                 types: tuple[str, ...]) -> RunObservation:
    """One (case, repeat) whose ANSWER carried `types`. Only the answer hops'
    `pii_type` reaches `draw_sample`, so the rest stays the smallest legal
    shape the fixtures already build."""
    hops = tuple(_hop("OUT", "answer", item_id, index, 0, "", -1, -1, "")
                 for index, item_id in enumerate(("p1", "p2")[:len(types)]))
    case = _case(case_id, behaviour, ("Иванова Елена, +7 916 402-11-87",),
                 (NAME_ITEM, PHONE_ITEM), hops)
    case = replace(case, base=replace(case.base, register=register))
    observed = tuple(HopObservation(case_id=case_id, repeat=repeat, hop=hop, declared=True,
                                    pii_type=pii_type, produced="", reference="",
                                    status="absent", verdict=None)
                     for hop, pii_type in zip(hops, types))
    return RunObservation(case=case, repeat=repeat, hops=observed, run=_run(case_id),
                          ic=None, cc=None)


def _population() -> list[RunObservation]:
    """Eight strata (2 families × 2 registers × 2 type sets), six answers each."""
    out: list[RunObservation] = []
    for behaviour in ("single", "rag"):
        for register in ("chat", "voice_raw"):
            for types in (("NAME",), ("NAME", "PHONE")):
                for index in range(6):
                    out.append(_observation(
                        f"{behaviour}-{register}-{len(types)}-{index:02d}", 0,
                        behaviour, register, types))
    return out


def _records(count: int, pii_type: str, agree: int, label_a: str, label_b: str,
             prefix: str) -> list[CalibrationRecord]:
    """`count` labelled rows of one type, `agree` of which the judge got right.
    The human labels alternate, so neither rater is constant and κ is defined."""
    out: list[CalibrationRecord] = []
    for index in range(count):
        human = label_a if index % 2 == 0 else label_b
        judge = human if index < agree else (label_b if human == label_a else label_a)
        out.append(CalibrationRecord(
            sample_id=f"{prefix}-{index:04d}", case_id=f"{prefix}-{index:04d}",
            pii_types=(pii_type,), family="single", register="chat", holdout=False,
            human_label=human, judge_label=judge, judge_reason="", repeat_index=0,
            judge_model=MODEL, prompt_sha256=PROMPT))
    return out


def _stable_repeats(rows: list[CalibrationRecord], how_many: int,
                    disagreeing: int) -> list[CalibrationRecord]:
    """K-1 more rows per answer for the stability sub-sample.

    HAND-WRITTEN LABELS, and they pin the ARITHMETIC of `repeat_check` only.
    That the pipeline can produce a disagreeing group at all is a different
    claim and is pinned by `test_repeats_are_real_judge_calls`, which asks a
    scripted judge K times — before that existed, this fixture was the only
    non-zero spread in the repository and the threshold could not fire on
    anything a run produced.
    """
    out: list[CalibrationRecord] = []
    for position, one in enumerate(rows[:how_many]):
        for index in range(1, CALIBRATION.repeats):
            label = one.judge_label if position >= disagreeing else "выдумал"
            out.append(replace(one, repeat_index=index, judge_label=label))
    return out


def test_no_pseudex() -> list[str]:
    loaded = sorted(name for name in sys.modules if name.startswith("pseudex"))
    return [] if not loaded else [f"калибровка потянула движок: {loaded}"]


def test_sample_strata() -> list[str]:
    failures: list[str] = []
    thresholds = replace(CALIBRATION, sample_size=24, per_stratum_min=2, holdout_share=0.25)
    population = _population()
    holdout = frozenset(one.case.base.id for one in population if one.case.base.id.endswith(("04", "05")))
    sample = c.draw_sample(population, thresholds, 5150, holdout, frozenset())
    if len(sample) != thresholds.sample_size:
        failures.append(f"выборка {len(sample)}, а не {thresholds.sample_size}")
    counts: dict[tuple[str, str, str], int] = {}
    for one in sample:
        counts[(("+".join(one.pii_types)), one.family, one.register)] = counts.get(
            (("+".join(one.pii_types)), one.family, one.register), 0) + 1
    if len(counts) != 8:
        failures.append(f"страт в выборке {len(counts)}, а в популяции 8: {sorted(counts)}")
    thin = {name: count for name, count in counts.items() if count < thresholds.per_stratum_min}
    if thin:
        failures.append(f"страты ниже пола {thresholds.per_stratum_min}: {thin}")
    picked_holdout = sum(1 for one in sample if one.holdout)
    if picked_holdout < int(round(len(sample) * thresholds.holdout_share)):
        failures.append(f"из holdout взято {picked_holdout}, нужно "
                        f"{int(round(len(sample) * thresholds.holdout_share))}")
    if any(one.human_label or one.judge_label for one in sample):
        failures.append("свежая выборка уже размечена")
    if len({one.sample_id for one in sample}) != len(sample):
        failures.append("в выборке повторяются sample_id")
    # Deterministic: the same seed draws the same rows, or a calibration could
    # not be re-derived from the file it was built from.
    if c.draw_sample(population, thresholds, 5150, holdout, frozenset()) != sample:
        failures.append("та же выборка при том же зерне вышла другой")
    if c.draw_sample(population, thresholds, 6060, holdout, frozenset()) == sample:
        failures.append("другое зерно дало ту же выборку — зерно ни на что не влияет")
    # The NEGATIVE: answers with no personal data cannot be stratified by type.
    empty = [replace(one, hops=()) for one in population]
    try:
        c.draw_sample(empty, thresholds, 5150, frozenset(), frozenset())
        failures.append("выборка построена из ответов без ПД")
    except c.CalibrationError:
        pass
    return failures


def test_repeats_never_duplicate_index_zero() -> list[str]:
    """The drawn sample already holds each answer at `repeat_index` 0. A
    sub-sample that emitted index 0 again would count fifty answers twice in an
    agreement they are not about — the export wrote exactly that until the
    range started at 1."""
    thresholds = replace(CALIBRATION, sample_size=24, per_stratum_min=2, repeat_sample=4)
    sample = c.draw_sample(_population(), thresholds, 5150, frozenset(), frozenset())
    extra = c.draw_repeats(sample, thresholds, 5150)
    failures: list[str] = []
    if any(one.repeat_index == 0 for one in extra):
        failures.append("подвыборка на устойчивость повторила строку с repeat_index 0")
    if len(extra) != thresholds.repeat_sample * (thresholds.repeats - 1):
        failures.append(f"повторов {len(extra)}, ожидалось "
                        f"{thresholds.repeat_sample * (thresholds.repeats - 1)}")
    if not c.has_repeats(list(sample) + list(extra)):
        failures.append("после добавления повторов подвыборка всё ещё не видна")
    if c.has_repeats(list(sample)):
        failures.append("в выборке без повторов has_repeats сказал «есть» — "
                        "тогда спред считался бы на пустом месте")
    return failures


def test_kappa_known_values() -> list[str]:
    """A textbook 2×2: both yes 45, human-yes/judge-no 15, human-no/judge-yes 10,
    both no 30. po = 0.75, pe = 0.6·0.55 + 0.4·0.45 = 0.51, κ = 0.4898."""
    failures: list[str] = []
    rows: list[CalibrationRecord] = []

    def add(human: str, judge: str, count: int, tag: str) -> None:
        for index in range(count):
            rows.append(CalibrationRecord(
                sample_id=f"{tag}-{index}", case_id=f"{tag}-{index}", pii_types=("NAME",),
                family="single", register="chat", holdout=False, human_label=human,
                judge_label=judge, judge_reason="", repeat_index=0, judge_model=MODEL,
                prompt_sha256=PROMPT))

    add("верно", "верно", 45, "a")
    add("верно", "неверно", 15, "b")
    add("неверно", "верно", 10, "c")
    add("неверно", "неверно", 30, "d")
    value = c.kappa(rows)
    if abs(value - 0.4898) > 0.001:
        failures.append(f"κ на учебной таблице {value:.4f}, ожидалось 0.4898")
    if abs(c.agreement(rows) - 0.75) > 1e-9:
        failures.append(f"сырое согласие {c.agreement(rows):.4f}, ожидалось 0.75")
    # A constant rater: κ is undefined and we refuse rather than certify.
    constant = [replace(one, human_label="верно", judge_label="верно") for one in rows]
    if c.kappa(constant) != 0.0:
        failures.append("постоянный судья на постоянной разметке получил κ != 0")
    # A `none` verdict is a disagreement, never an exclusion — otherwise a
    # judge that answers nothing calibrates on an empty denominator.
    silent = [replace(one, judge_label="none") for one in rows]
    if c.agreement(silent) != 0.0:
        failures.append("вердикты «none» не посчитались расхождением")
    try:
        c.agreement([])
        failures.append("согласие посчиталось на пустой выборке")
    except c.CalibrationError:
        pass
    return failures


def test_repeat_check() -> list[str]:
    failures: list[str] = []
    rows = _records(4, "NAME", 4, "верно", "неверно", "rep")
    rows += _stable_repeats(rows, 4, 1)
    value = c.repeat_check(rows)
    if abs(value - 0.25) > 1e-9:
        failures.append(f"спред {value}, ожидался 0.25 (один ответ из четырёх разошёлся)")
    if c.repeat_check(_records(4, "NAME", 4, "верно", "неверно", "rep")
                      + _stable_repeats(rows, 4, 0)) != 0.0:
        failures.append("полностью устойчивый судья получил ненулевой спред")
    try:
        c.repeat_check(_records(4, "NAME", 4, "верно", "неверно", "solo"))
        failures.append("спред посчитан там, где повторов не было")
    except c.CalibrationError:
        pass
    return failures


def test_thresholds() -> list[str]:
    failures: list[str] = []
    size = CALIBRATION.sample_size
    # 0.84 agreement — below the 0.85 bar, everything else fine.
    weak = _records(size, "NAME", int(size * 0.84), "верно", "неверно", "weak")
    weak += _stable_repeats(weak, CALIBRATION.repeat_sample, 0)
    low = c.stamp(weak, MODEL, PROMPT)
    if low.calibrated:
        failures.append(f"судья при согласии {low.raw_agreement:.2f} признан откалиброванным")
    # 0.90 agreement, κ ≈ 0.80, spread 0 — calibrated.
    good = _records(size, "NAME", int(size * 0.90), "верно", "неверно", "good")
    good += _stable_repeats(good, CALIBRATION.repeat_sample, 0)
    ok = c.stamp(good, MODEL, PROMPT)
    if not ok.calibrated:
        failures.append(f"годный судья не прошёл: согласие {ok.raw_agreement:.2f} "
                        f"κ {ok.kappa:.2f} спред {ok.repeat_disagreement:.2f} n {ok.n}")
    # One type with ≥ 20 examples at κ 0.5 sinks the whole stamp.
    mixed = list(good) + _records(40, "PHONE", 30, "верно", "неверно", "phone")
    sunk = c.stamp(mixed, MODEL, PROMPT)
    if sunk.calibrated:
        failures.append(f"тип с κ {sunk.per_type_kappa.get('PHONE')} не уронил штамп")
    if "PHONE" not in sunk.per_type_kappa:
        failures.append("тип с 40 примерами не попал в по-типовую κ")
    # A type below the floor is not reported at all: κ on twelve examples is noise.
    rare = list(good) + _records(12, "CARD", 12, "верно", "неверно", "card")
    if "CARD" in c.stamp(rare, MODEL, PROMPT).per_type_kappa:
        failures.append("тип ниже per_type_min_examples попал в штамп")
    # Too few rows: the spec's sample is 300 and a perfect twenty is not one.
    tiny = _records(20, "NAME", 20, "верно", "неверно", "tiny")
    tiny += _stable_repeats(tiny, 20, 0)
    if c.stamp(tiny, MODEL, PROMPT).calibrated:
        failures.append("штамп на 20 ответах объявлен калибровкой")
    # No stability sub-sample: the question was not asked, and that is 1.0.
    lonely = c.stamp(_records(size, "NAME", int(size * 0.95), "верно", "неверно", "solo"),
                     MODEL, PROMPT)
    if lonely.repeat_disagreement != 1.0 or lonely.calibrated:
        failures.append(f"без подвыборки на устойчивость спред {lonely.repeat_disagreement}")
    # Rows of ANOTHER prompt do not count towards this prompt's calibration.
    foreign = [replace(one, prompt_sha256="b" * 64) for one in good]
    if c.stamp(foreign, MODEL, PROMPT).n != 0:
        failures.append("строки другого промпта посчитались калибровкой этого")
    return failures


def test_recalibration_triggers() -> list[str]:
    failures: list[str] = []
    good = CalibrationStamp(judge_model=MODEL, prompt_sha256=PROMPT, n=300, raw_agreement=0.9,
                            kappa=0.8, per_type_kappa={"NAME": 0.8}, repeat_disagreement=0.0,
                            calibrated=True)
    if not c.is_current(good, MODEL, PROMPT, "d1", "d1", 0.0):
        failures.append("свежая калибровка объявлена устаревшей")
    if c.is_current(good, "claude-opus-5", PROMPT, "d1", "d1", 0.0):
        failures.append("смена модели судьи не потребовала пере-калибровки")
    if c.is_current(good, MODEL, "c" * 64, "d1", "d1", 0.0):
        failures.append("смена промпта не потребовала пере-калибровки")
    if c.is_current(good, MODEL, PROMPT, "d2", "d1", CALIBRATION.recalibrate_on_corpus_change):
        failures.append("корпус сдвинулся на порог, а калибровка осталась действующей")
    if not c.is_current(good, MODEL, PROMPT, "d2", "d1", 0.05):
        failures.append("корпус сдвинулся на 5% — этого мало, чтобы отменять калибровку")
    if c.is_current(replace(good, calibrated=False), MODEL, PROMPT, "d1", "d1", 0.0):
        failures.append("некалиброванный штамп объявлен действующим")
    return failures


def test_import_refuses_bad_label() -> list[str]:
    failures: list[str] = []
    # Blank judge labels: the exported sheet is BLIND (T9), and `read_sheet`
    # refuses a row that carries the judge\'s verdict — see `test_sheet_is_blind`.
    rows = [replace(one, judge_label="", judge_reason="")
            for one in _records(2, "NAME", 2, "верно", "неверно", "sheet")]
    with tempfile.TemporaryDirectory() as tmp:
        sheet = Path(tmp) / "sheet.jsonl"
        for one in rows:
            row = r.calibration_record_to_json(one)
            row["restored_answer"] = "курьер приедет"          # dropped on import
            row["answer_sha256"] = c.answer_digest("курьер приедет")
            r.append_row(sheet, row)
        parsed = c.read_sheet(sheet)
        if len(parsed) != 2 or parsed[0].human_label != "верно":
            failures.append(f"размеченный лист прочитан неверно: {parsed}")
        bad = Path(tmp) / "bad.jsonl"
        row = r.calibration_record_to_json(rows[0])
        row["human_label"] = "ок"
        r.append_row(bad, row)
        try:
            c.read_sheet(bad)
            failures.append("лист с меткой вне JUDGE_LABELS принят")
        except c.CalibrationError as refused:
            if "human_label" not in str(refused):
                failures.append(f"отказ не называет поле: {refused}")
        empty = Path(tmp) / "empty.jsonl"
        row = r.calibration_record_to_json(rows[0])
        row["human_label"] = ""
        r.append_row(empty, row)
        try:
            c.read_sheet(empty)
            failures.append("неразмеченная строка принята как калибровка")
        except c.CalibrationError:
            pass
    return failures


# --- a run directory, built from records alone (no engine, no model) --------------------

def _run_dir(root: Path, gated_id: str,
             run_of: Callable[[CaseV5], ArmRunV5]) -> Path:
    """The smallest directory `observations_of` accepts, with ONE answer decided
    by the residual pre-gate.

    Built from `records` writers rather than from `harness.drive_v5`: the
    harness imports the engine and this module must not
    (`test_no_pseudex`), so the run this file reads is written by the same
    serialisers the real one is written by and by nothing else.

    `run_of` is explicit at every call site rather than defaulted, because the
    sheet and the K repeats are about WHICH substitutes a record carries, and a
    default would have every check but one silently read the same record.
    """
    run_dir = root / "v5-live-nano"
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = ArmMeta("fixture", 1, 0, "sess", "success", False, None, (), "", 0.0)
    cases = [_answer_case(case_id) for case_id in ANSWER_IDS]
    (run_dir / "corpus.v5.json").write_text(json.dumps(
        {"corpus": [case_v5_to_json(case) for case in cases], "digest": "digest-v5"},
        ensure_ascii=False), encoding="utf-8")
    judge = r.run_file(run_dir, RUN_ID, "<run>.judge.jsonl")
    for case in cases:
        run = run_of(case)
        r.append_row(r.run_file(run_dir, RUN_ID, "<run>.arms.jsonl"),
                     {"case_id": case.base.id, "repeat": 0, "arm": "I", "termination": "done"})
        r.append_row(r.run_file(run_dir, RUN_ID, "<run>.arms.v5.jsonl"),
                     r.arm_v5_record(run, meta, case.base))
        r.append_row(r.run_file(run_dir, RUN_ID, "<run>.hops.jsonl"),
                     r.hop_observation_to_json(HopObservation(
                         case_id=case.base.id, repeat=0, hop=case.hops[0], declared=True,
                         pii_type="NAME", produced=NAME_ITEM.value, reference=NAME_ITEM.value,
                         status="observed", verdict=form_match("NAME", NAME_ITEM.value,
                                                               NAME_ITEM.value))))
        pregate = case.base.id == gated_id
        r.append_row(judge, r.judge_row_to_json(r.JudgeRow(
            case_id=case.base.id, repeat=0, input_sha256="a" * 64,
            verdict=JudgeVerdict(
                label="неверно" if pregate else "верно",
                reason="подмена в ответе: «Пахомова»" if pregate else "запись та же · цитата: «Иванова»",
                judged_by="residual_gate" if pregate else "model",
                cost_usd=0.0 if pregate else 0.01))))
    return run_dir


def _answer_case(case_id: str) -> CaseV5:
    """A case whose ANSWER carried a NAME — the only shape `draw_sample`
    stratifies."""
    hops = (_hop("OUT", "answer", "p1", 0, 0, "", -1, -1, ""),)
    return _case(case_id, "single", ("Иванова Елена, +7 916 402-11-87",),
                 (NAME_ITEM, PHONE_ITEM), hops)


def _answer_run(case: CaseV5) -> ArmRunV5:
    run = _with_subs(_run(case.base.id), {"p1": SUBSTITUTE})
    return _with_replies(run, f"Передал {SUBSTITUTE}.",
                         f"Передал {NAME_ITEM.value} по адресу.", "контроль")


def test_sample_excludes_pregate_verdicts() -> list[str]:
    """T11: a verdict the residual pre-gate gave is not the model\'s, and κ over
    it measures a human agreeing with `str.casefold() in`.

    Both numbers the report certifies («судья claude-sonnet-5, κ=…») are
    statements about the MODEL that will judge the next run, so the answers it
    was never asked about are out of the draw — not filtered afterwards, which
    would leave the spec\'s 300 as 300-minus-however-many.
    """
    failures: list[str] = []
    thresholds = replace(CALIBRATION, sample_size=24, per_stratum_min=2, holdout_share=0.0)
    population = _population()
    gated = frozenset((one.case.base.id, one.repeat) for one in population[:12])
    sample = c.draw_sample(population, thresholds, 5150, frozenset(), gated)
    drawn = {c._split_sample_id(one.sample_id) for one in sample}
    if drawn & gated:
        failures.append(f"в выборку попали ответы, решённые претгейтом: {sorted(drawn & gated)}")
    # The NEGATIVE: without the exclusion those same answers ARE drawn, so the
    # argument does work rather than describing a population that never had them.
    open_draw = c.draw_sample(population, thresholds, 5150, frozenset(), frozenset())
    if not {c._split_sample_id(one.sample_id) for one in open_draw} & gated:
        failures.append("без исключения претгейтных ответов выборка всё равно их не взяла — "
                        "проверка ни о чём")
    # Everything gated is «калибровать не на чем», by name.
    everything = frozenset((one.case.base.id, one.repeat) for one in population)
    try:
        c.draw_sample(population, thresholds, 5150, frozenset(), everything)
        failures.append("выборка построена из одних претгейтных ответов")
    except c.CalibrationError as refused:
        if "претгейт" not in str(refused):
            failures.append(f"отказ не называет претгейт: {refused}")
    # And the reader that tells them apart reads `judged_by`, not the label.
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _run_dir(Path(tmp), ANSWER_IDS[0], _answer_run)
        verdicts = c.judge_verdicts_of(run_dir)
        if c.gated_answers(verdicts) != frozenset({(ANSWER_IDS[0], 0)}):
            failures.append(f"претгейтные ответы прогона прочитаны как {c.gated_answers(verdicts)}")
        if len(verdicts) != len(ANSWER_IDS):
            failures.append(f"вердиктов прогона прочитано {len(verdicts)}, а их {len(ANSWER_IDS)}")
    return failures


def test_sheet_is_blind() -> list[str]:
    """T9: the labeller is handed the ANSWER, never the judge\'s verdict.

    `sheet_rows` used to write `judge_label` and `judge_reason` — the latter
    carrying the judge\'s verbatim quote and rationale — into the very row whose
    `human_label` the human was about to fill. κ and raw agreement are agreement
    between two INDEPENDENT raters, and both gate circulation.
    """
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = _run_dir(root, ANSWER_IDS[0], _answer_run)
        thresholds = replace(CALIBRATION, sample_size=2, per_stratum_min=1, holdout_share=0.0)
        gated = c.gated_answers(c.judge_verdicts_of(run_dir))
        sample = c.draw_sample(c.observations_of(run_dir), thresholds, 5150, frozenset(), gated)
        rows = c.sheet_rows(run_dir, sample, MODEL)
        if not rows:
            return ["лист разметки пуст — проверять нечего"]
        for row in rows:
            if row["judge_label"] or row["judge_reason"]:
                failures.append(f"в листе разметки метка судьи: {row['judge_label']!r} "
                                f"{row['judge_reason']!r}")
            for key in ("restored_answer", "answer_sha256", "oracle_literals",
                        "dialogue_context", "customer_question"):
                if key not in row:
                    failures.append(f"в листе нет того, что видел судья: {key}")
            if "цитата" in json.dumps(row, ensure_ascii=False):
                failures.append("в строку листа просочилась цитата судьи")
            if row["answer_sha256"] != c.answer_digest(str(row["restored_answer"])):
                failures.append("хэш ответа в листе не от того ответа")
        # A filled sheet that CARRIES a judge label is refused: the blind rule
        # survives the next helpful edit only if the reader enforces it.
        sheet = root / "sheet.jsonl"
        for row in rows:
            r.append_row(sheet, {**row, "human_label": "верно"})
        try:
            if len(c.read_sheet(sheet)) != len(rows):
                failures.append("слепой размеченный лист не прочитался")
        except c.CalibrationError as refused:
            # Reported, not raised: the likeliest cause is that `sheet_rows`
            # started writing the judge's verdict again, which is the defect
            # this check is about.
            failures.append(f"лист, который экспортировал сам инструмент, не читается: {refused}")
        sighted = root / "sighted.jsonl"
        r.append_row(sighted, {**rows[0], "human_label": "верно", "judge_label": "верно"})
        try:
            c.read_sheet(sighted)
            failures.append("лист с меткой судьи принят — κ мерила бы якорение")
        except c.CalibrationError as refused:
            if "judge_label" not in str(refused):
                failures.append(f"отказ не называет поле: {refused}")
    return failures


class _ScriptedJudge:
    """K answers, in order, per call — the judge a live run cannot script.

    `repeat_disagreement` is a statement about the judge\'s OWN spread, so the
    fixture that must make it non-zero is a judge that answers differently to
    the same question; a fixture that hand-wrote the labels into the sheet (the
    only non-zero spread in the repo before) proved the arithmetic and never
    the pipeline.
    """

    def __init__(self, labels: tuple[str, ...]) -> None:
        self._labels = labels
        self.asked = 0

    async def __call__(self, request: JudgeInput, minted: tuple[str, ...]) -> JudgeVerdict:
        label = self._labels[self.asked % len(self._labels)]
        self.asked += 1
        if minted and any(surface in request.restored_answer for surface in minted):
            return JudgeVerdict(label="", reason="подмена в ответе", judged_by="none",
                                cost_usd=0.0)
        return JudgeVerdict(label=label, reason=f"цитата: «{request.restored_answer[:10]}»",
                            judged_by="model", cost_usd=0.001)


def test_repeats_are_real_judge_calls() -> list[str]:
    """T10: the K stability rows are K REAL verdicts, so `repeat_disagreement`
    can be non-zero on something the pipeline produced.

    The harness asks the judge once per (case, repeat); `sheet_rows` then looked
    that ONE verdict up for every repeat row, so all K labels of an answer were
    equal by construction and the threshold that refuses an unstable judge
    could never fire. The spec asks for K=3 repeats (§8.5) — they are spent
    here, in `export --repeats`.
    """
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = _run_dir(root, ANSWER_IDS[0], _answer_run)
        thresholds = replace(CALIBRATION, sample_size=2, per_stratum_min=1, holdout_share=0.0,
                             repeat_sample=2, repeats=3)
        gated = c.gated_answers(c.judge_verdicts_of(run_dir))
        sample = c.draw_sample(c.observations_of(run_dir), thresholds, 5150, frozenset(), gated)
        repeats = c.draw_repeats(sample, thresholds, 5150)
        unstable = _ScriptedJudge(("верно", "частично"))
        verdicts = asyncio.run(c.ask_repeats(run_dir, repeats, unstable))
        if unstable.asked != len(repeats):
            failures.append(f"судью спросили {unstable.asked} раз на {len(repeats)} повторов")
        if len(verdicts) != len(repeats):
            failures.append(f"вердиктов {len(verdicts)}, повторов {len(repeats)}")
        by_sample: dict[str, set[str]] = {}
        for one in verdicts:
            by_sample.setdefault(one.sample_id, set()).add(one.label)
        if not any(len(labels) > 1 for labels in by_sample.values()):
            failures.append("K вердиктов одного ответа совпали у НЕустойчивого судьи — "
                            "метки всё ещё берутся из одного просмотра")
        # …and the number the threshold reads follows from them.
        shown = c.answers_of(run_dir)
        labelled = tuple(replace(one, human_label="верно") for one in sample)
        joined = c.join_judge_labels(labelled, c.judge_verdicts_of(run_dir), verdicts,
                                     shown, shown)
        spread = c.repeat_check(joined)
        if spread <= 0.0:
            failures.append(f"спред неустойчивого судьи {spread} — порог не может сработать")
        # THE NEGATIVE: a judge that always says the same thing has spread 0.0,
        # or the number above would be an artefact of the scripted fixture.
        steady = _ScriptedJudge(("верно",))
        same = asyncio.run(c.ask_repeats(run_dir, repeats, steady))
        joined_steady = c.join_judge_labels(labelled, c.judge_verdicts_of(run_dir), same,
                                            shown, shown)
        if c.repeat_check(joined_steady) != 0.0:
            failures.append("устойчивый судья получил ненулевой спред")
        # The repeats file is written beside the sheet and read back verbatim.
        path = c.repeats_path(root / "sheet.jsonl")
        path.write_text("".join(json.dumps(c.repeat_verdict_to_json(one), ensure_ascii=False,
                                           sort_keys=True) + "\n" for one in verdicts),
                        encoding="utf-8")
        if c.read_repeats(path) != verdicts:
            failures.append("повторы судьи прочитались не теми, что записаны")
        broken = root / "broken.repeats.jsonl"
        r.append_row(broken, {**c.repeat_verdict_to_json(verdicts[0]), "repeat_index": 0})
        try:
            c.read_repeats(broken)
            failures.append("повтор с индексом 0 принят — ответ посчитали бы дважды")
        except c.CalibrationError:
            pass
    return failures


def test_import_joins_and_stamps_the_run() -> list[str]:
    """F3.5: a filled sheet becomes the run\'s own stamp.

    Without this path a report is «НЕ ОТКАЛИБРОВАН» for ever — not because the
    judge failed a threshold, but because nobody could tell the run otherwise:
    the stamp lives in row 0 of `<run>.judge.jsonl` and only the harness ever
    wrote it, always as «не откалиброван».
    """
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        run_dir = _run_dir(root, ANSWER_IDS[0], _answer_run)
        thresholds = replace(CALIBRATION, sample_size=2, per_stratum_min=1, holdout_share=0.0)
        gated = c.gated_answers(c.judge_verdicts_of(run_dir))
        sample = c.draw_sample(c.observations_of(run_dir), thresholds, 5150, frozenset(), gated)
        filled = tuple(replace(one, human_label="верно", judge_model=MODEL,
                               prompt_sha256=c.prompt_sha256()) for one in sample)
        shown = c.answers_of(run_dir)
        joined = c.join_judge_labels(filled, c.judge_verdicts_of(run_dir), (), shown, shown)
        if any(not one.judge_label for one in joined):
            failures.append("после стыковки остались строки без метки судьи")
        if any(one.judge_reason == "" for one in joined):
            failures.append("после стыковки потерялась причина вердикта")
        # The run learns the number: row 0 of the judge file, verdicts intact.
        before = len(r.read_rows(r.run_file(run_dir, RUN_ID, "<run>.judge.jsonl")))
        c.write_stamp(run_dir, RUN_ID, c.stamp(joined, MODEL, c.prompt_sha256()))
        rows = r.read_rows(r.run_file(run_dir, RUN_ID, "<run>.judge.jsonl"))
        if "calibrated" not in rows[0]:
            failures.append("штамп не встал нулевой строкой — report.judge_half его не найдёт")
        if len(rows) != before + 1:
            failures.append(f"штамп съел вердикты: было {before}, стало {len(rows)}")
        c.write_stamp(run_dir, RUN_ID, c.stamp(joined, MODEL, c.prompt_sha256()))
        if len(r.read_rows(r.run_file(run_dir, RUN_ID, "<run>.judge.jsonl"))) != before + 1:
            failures.append("второй штамп добавил строку вместо замены")
        # An answer that moved under the label is refused BY NAME: the human
        # labelled a text, not a pair of ids.
        moved = dict(shown)
        moved[filled[0].sample_id] = c.answer_digest("другой ответ")
        try:
            c.join_judge_labels(filled, c.judge_verdicts_of(run_dir), (), shown, moved)
            failures.append("стыковка приняла ответ, изменившийся после экспорта")
        except c.CalibrationError as refused:
            if "изменился" not in str(refused):
                failures.append(f"отказ не называет причину: {refused}")
        # A pre-gated answer must never reach the join either.
        pregated = tuple(replace(one, sample_id=f"{ANSWER_IDS[0]}|0", case_id=ANSWER_IDS[0])
                         for one in filled[:1])
        try:
            c.join_judge_labels(pregated, c.judge_verdicts_of(run_dir), (), shown, shown)
            failures.append("в калибровку попал вердикт претгейта")
        except c.CalibrationError:
            pass
        # And an answer the judge was never asked about.
        unknown = tuple(replace(one, sample_id="нет-такого|0", case_id="нет-такого")
                        for one in filled[:1])
        try:
            c.join_judge_labels(unknown, {}, (), shown, shown)
            failures.append("в калибровку попала строка без вердикта прогона")
        except c.CalibrationError:
            pass
    return failures


# --- G3.4 / G3.6: the sheet and the repeats read what the RUN's judge read ------------

# One substitute per place the record keeps them. `base.substitutes` is the
# only one `minted_of` used to read; the other two are how the model met a
# second spelling in a later message and a value inside a TOOL RESULT.
MENTIONED: str = "Пахомовой Ольге"
IN_RESULT: str = "Кудрявцев Пётр"


def _leaky_run(case: CaseV5) -> ArmRunV5:
    """A run whose INTERMEDIATE turn carries all three substitutes.

    The restorer leaving a lower-cased or inflected substitute standing in an
    earlier turn is the ordinary case on this corpus's chat/sloppy/voice
    registers — `judge.masked_dialogue` replaces it with `RESIDUAL_MARKER` and
    counts it, and the human's sheet must show the same marker or κ compares
    two different tasks.
    """
    run = _with_subs(_run(case.base.id), {"p1": SUBSTITUTE})
    run = _with_replies(run, f"Передал {SUBSTITUTE}.",
                        f"Передал {NAME_ITEM.value} по адресу.", "контроль")
    result = ToolResultRecord(
        tool_name="crm_find_contact", seq=1, call_ordinal=0, turn=1, return_form="single",
        text_real=NAME_ITEM.value, text_masked=IN_RESULT,
        spans_real={"p1": (0, len(NAME_ITEM.value))},
        pieces=((0, len(NAME_ITEM.value), IN_RESULT, "NAME"),), forced=False)
    earlier = (f"Секунду: {SUBSTITUTE}, {MENTIONED}, {IN_RESULT}.", run.turn_replies[0])
    return replace(run, turn_replies=earlier, tool_results=(result,),
                   mentions=(MentionRecord(item_id="p1", msg=1, result_seq=-1,
                                           substitute=MENTIONED, request_index=1),))


def test_minted_of_is_the_runs_own_list() -> list[str]:
    """G3.6: the K repeats masked their prompt with a NARROWER list than the run.

    `minted_of` read `base.substitutes` alone — one surface per DECLARED item —
    while the run judged with everything the gateway minted. On 67 of 400
    corpus cases the two lists differed, and on 6 of them a repeat's prompt KEPT
    a substitute the run's prompt had masked out: `repeat_disagreement` then
    measured the mask instead of the judge, which is the one thing that number
    must not do.
    """
    failures: list[str] = []
    case = _answer_case(ANSWER_IDS[0])
    observation = RunObservation(case=case, repeat=0, hops=(), run=_leaky_run(case),
                                 ic=None, cc=None)
    minted = c.minted_of(observation)
    for surface, where in ((SUBSTITUTE, "base.substitutes"), (MENTIONED, "mentions"),
                           (IN_RESULT, "tool_results")):
        if surface not in minted:
            failures.append(f"подмена из {where} не попала в список прогона: {minted}")
    if list(minted) != sorted(minted):
        failures.append(f"список не отсортирован — порядок замен станет вторым списком: {minted}")
    # THE NEGATIVE: the old reading really was narrower, so the widening does
    # work rather than describing a record that never held the other two.
    narrow = tuple(value[0] for value in observation.run.base.substitutes.values() if value[0])
    if set(minted) <= set(narrow):
        failures.append("широкий список не шире прежнего — проверка ни о чём")
    return failures


def test_the_sheet_shows_the_masked_dialogue() -> list[str]:
    """G3.4: κ is agreement between two raters ON ONE TASK.

    The judge never sees a substitute the restorer left in an earlier turn —
    `build_prompt` goes through `masked_dialogue` — while the «blind» sheet
    printed the raw turn, so the human read a fake name where the judge read
    «[нераскрытая подмена]» and answered a different question about the
    context (rubric question 4).
    """
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = _run_dir(Path(tmp), ANSWER_IDS[0], _leaky_run)
        thresholds = replace(CALIBRATION, sample_size=2, per_stratum_min=1, holdout_share=0.0)
        gated = c.gated_answers(c.judge_verdicts_of(run_dir))
        sample = c.draw_sample(c.observations_of(run_dir), thresholds, 5150, frozenset(), gated)
        rows = c.sheet_rows(run_dir, sample, MODEL)
        if not rows:
            return ["лист разметки пуст — проверять нечего"]
        shown = "\n".join(str(turn["text"]) for row in rows
                           for turn in row["dialogue_context"])   # type: ignore[union-attr]
        for surface in (SUBSTITUTE, MENTIONED, IN_RESULT):
            if surface in shown:
                failures.append(f"в листе разметки стоит подмена {surface!r}, "
                                f"а судья читал маркер")
        if judge.RESIDUAL_MARKER not in shown:
            failures.append("в листе разметки нет маркера — маскирование не применялось")
        # THE NEGATIVE: the UNMASKED dialogue — what the sheet used to carry —
        # really does hold those substitutes, so their absence above is the
        # masking and not an empty dialogue.
        observations = {(one.case.base.id, one.repeat): one for one in c.observations_of(run_dir)}
        raw: list[str] = []
        for row in rows:
            case_id, repeat = c._split_sample_id(str(row["sample_id"]))
            one = observations[(case_id, repeat)]
            raw += [turn.text for turn in c.judge_input(one.case, one.run).dialogue_context]
        if SUBSTITUTE not in "\n".join(raw):
            failures.append("незамаскированный диалог не содержит подмены — негатив ни о чём")
    return failures


# --- the whole loop, offline: export -> labelling -> repeats -> import -> stamp ---------

# Шесть страт (2 семьи × 3 регистра) по шестьдесят ответов: выборка спеки —
# 300 строк при поле в 20 на страту, и корпус, в котором их меньше, проверяет
# не путь, а пониженные пороги.
STRATA: tuple[tuple[str, str], ...] = (
    ("single", "chat"), ("single", "voice_raw"), ("single", "sloppy"),
    ("rag", "chat"), ("rag", "voice_raw"), ("rag", "sloppy"))
PER_STRATUM: int = 60
# Каждый двадцать пятый ответ судья и человек читают по-разному. Не ноль:
# при полном согласии κ описывает выборку, на которой разметчик мог быть
# константой, а порог, который не может не пройти, ничего не сертифицирует.
DISAGREE_EVERY: int = 25


def _calibratable_case(case_id: str, behaviour: str, register: str) -> CaseV5:
    case = _answer_case(case_id)
    return replace(case, behaviour=behaviour, base=replace(case.base, register=register))


def _calibratable_run(root: Path, holdout: frozenset[str]) -> tuple[Path, list[CaseV5]]:
    """Каталог прогона, на котором калибровка МОЖЕТ пройти.

    Написан теми же сериализаторами `records`, что и живой (`_run_dir` говорит
    почему), но большой: пороги спеки читаются из `contracts.CALIBRATION` и
    флагом не опускаются, так что путь «лист → разметка → штамп» можно
    проверить целиком только на корпусе, где 300 размеченных строк существуют.
    Вердикты судьи чередуются, иначе κ не определена и `stamp` вернёт 0.0.
    """
    run_dir = root / "v5-live-medium"
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = ArmMeta("fixture", 1, 0, "sess", "success", False, None, (), "", 0.0)
    cases: list[CaseV5] = []
    for behaviour, register in STRATA:
        for index in range(PER_STRATUM):
            cases.append(_calibratable_case(
                f"{behaviour}-{register}-{index:03d}", behaviour, register))
    (run_dir / "corpus.v5.json").write_text(json.dumps(
        {"corpus": [case_v5_to_json(case) for case in cases], "digest": "digest-v5"},
        ensure_ascii=False), encoding="utf-8")
    judge_path = r.run_file(run_dir, RUN_ID, "<run>.judge.jsonl")
    for case in cases:
        run = _answer_run(case)
        r.append_row(r.run_file(run_dir, RUN_ID, "<run>.arms.jsonl"),
                     {"case_id": case.base.id, "repeat": 0, "arm": "I", "termination": "done"})
        r.append_row(r.run_file(run_dir, RUN_ID, "<run>.arms.v5.jsonl"),
                     r.arm_v5_record(run, meta, case.base))
        r.append_row(r.run_file(run_dir, RUN_ID, "<run>.hops.jsonl"),
                     r.hop_observation_to_json(HopObservation(
                         case_id=case.base.id, repeat=0, hop=case.hops[0], declared=True,
                         pii_type="NAME", produced=NAME_ITEM.value, reference=NAME_ITEM.value,
                         status="observed",
                         verdict=form_match("NAME", NAME_ITEM.value, NAME_ITEM.value))))
        r.append_row(judge_path, r.judge_row_to_json(r.JudgeRow(
            case_id=case.base.id, repeat=0, input_sha256="a" * 64,
            verdict=JudgeVerdict(label=_judge_label(case.base.id),
                                 reason="запись та же · цитата: «Передал»",
                                 judged_by="model", cost_usd=0.01))))
    r.run_file(run_dir, RUN_ID, "<run>.meta.json").write_text(json.dumps(
        {"run_id": RUN_ID, "benchmark": "agentpii5", "model": "claude-haiku-4-5-20251001",
         "judge_model": MODEL, "tier": "medium", "repeats": 1, "digest": "digest-v5",
         "prompt_sha256": c.prompt_sha256()}, ensure_ascii=False), encoding="utf-8")
    # ШТАМП, КОТОРЫЙ ПИШЕТ САМ ПРОГОН: «не откалиброван», потому что сказать
    # ему обратное до разметки нечем. Именно его отчёт читает нулевой строкой.
    c.write_stamp(run_dir, RUN_ID, c.stamp((), MODEL, c.prompt_sha256()))
    (root / "ladder.json").write_text(json.dumps(
        {"version": 1, "seed": 5150, "corpus_sha256": "digest-v5",
         "tiers": {"holdout": sorted(holdout)}}, ensure_ascii=False), encoding="utf-8")
    return run_dir, cases


def _index_of(case_id: str) -> int:
    return int(case_id.rsplit("-", 1)[1])


def _judge_label(case_id: str) -> str:
    """Метка судьи — ФУНКЦИЯ ОТ ИМЕНИ СЛУЧАЯ, а не от позиции в файле.

    Лист разметки отсортирован по стратам, прогон записан в порядке семей, и
    метка, привязанная к номеру строки, склеивает человека с вердиктом другого
    ответа: согласие получилось 0.48 — ровно шум, — и проверка обвинила бы в
    этом пороги.
    """
    return "верно" if _index_of(case_id) % 2 == 0 else "частично"


def _human_label(case_id: str) -> str:
    """Метка человека: та же, что у судьи, кроме каждого DISAGREE_EVERY-го."""
    agreed = _judge_label(case_id)
    if _index_of(case_id) % DISAGREE_EVERY:
        return agreed
    return "частично" if agreed == "верно" else "верно"


class _RunEchoJudge:
    """Судья повторов, отвечающий то же, что записано в прогоне.

    Устойчивый судья — это `repeat_disagreement` = 0.0, и «устойчивый» здесь
    значит «согласный с самим собой», то есть со своим же вердиктом из
    `<run>.judge.jsonl`. Судья, который всегда говорит одно слово, на
    чередующихся вердиктах прогона даёт расхождение 0.46 — не потому, что
    он неустойчив, а потому, что это другой судья.
    """

    def __init__(self, label_of: Callable[[str], str]) -> None:
        self._label_of = label_of
        self.asked = 0

    async def __call__(self, request: JudgeInput, minted: tuple[str, ...]) -> JudgeVerdict:
        self.asked += 1
        return JudgeVerdict(label=self._label_of(request.case_id),
                            reason=f"цитата: «{request.restored_answer[:10]}»",
                            judged_by="model", cost_usd=0.0)


def _fill_sheet(sheet: Path, label_of: Callable[[str], str]) -> None:
    """То, что делает владелец руками: проставляет `human_label` в слепом листе."""
    rows = r.read_rows(sheet)
    sheet.write_text("".join(
        json.dumps({**row, "human_label": label_of(str(row["case_id"]))},
                   ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8")


def _script_the_repeats(run_dir: Path, sheet: Path, seed: int) -> int:
    """K−1 ПОВТОРОВ СУДЬИ БЕЗ МОДЕЛИ, в тот самый файл, который читает `import`.

    В живом пути эти вердикты покупает `export --repeats 3` (`_spend_repeats`)
    — это настоящие вызовы и настоящие деньги. Здесь на месте модели стоит
    `_ScriptedJudge`, и это ЕДИНСТВЕННОЕ, что подменено во всей проверке:
    выборка, лист, стыковка, пороги и штамп — тот же код, которым пойдёт
    владелец. Без повторов `repeat_check` не спрашивали, `stamp` ставит
    расхождение 1.0, и откалиброваться нельзя ничем.
    """
    sample = c.read_sheet(sheet)
    repeats = c.draw_repeats(sample, CALIBRATION, seed)
    verdicts = asyncio.run(c.ask_repeats(run_dir, repeats, _RunEchoJudge(_judge_label)))
    c.repeats_path(sheet).write_text("".join(
        json.dumps(c.repeat_verdict_to_json(one), ensure_ascii=False, sort_keys=True) + "\n"
        for one in verdicts), encoding="utf-8")
    return len(verdicts)


def _cli(argv: list[str]) -> int:
    """CLI как его зовёт владелец — через `main()`, а не мимо него.

    Проверка, которая дёргает `draw_sample` и `stamp` напрямую, зелёная и при
    сломанном `main`: разбор флагов, умолчание модели, поиск файла повторов и
    запись штампа живут именно там.
    """
    saved = sys.argv
    try:
        sys.argv = ["calibration", *argv]
        return c.main()
    finally:
        sys.argv = saved


def test_the_whole_loop_runs_offline() -> list[str]:
    """§8.5 ОТ НАЧАЛА ДО КОНЦА: `export` → разметка → `import` → штамп на
    прогоне → отчёт перестал быть НЕПОЛНЫМ по судье.

    Куски этого пути были проверены по одному и с ПОНИЖЕННЫМИ порогами
    (`sample_size=2`), так что ни одна проверка репозитория не видела
    `calibrated=True`, пришедшего из конвейера, — и ни одна не спрашивала
    отчёт, изменилось ли для него хоть что-нибудь. Пока так, «НЕПОЛНЫЙ: судья
    не откалиброван» стоит в каждом отчёте, и прочитать ось ответа нельзя
    никогда.

    ЕДИНСТВЕННОЕ, ЧТО ПОДМЕНЕНО, — модель: K−1 повторов судьи даёт
    `_ScriptedJudge`. Всё остальное — тот же `main()`, те же пороги
    `contracts.CALIBRATION`, тот же `report.judge_half`, который решает, что
    отчёт неполный.
    """
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Четверть случаев — holdout, и он приезжает ЛЕСТНИЦЕЙ, а не запятыми:
        # квота §8.5 в полтораста id руками не набирается.
        holdout = frozenset(f"{behaviour}-{register}-{index:03d}"
                            for behaviour, register in STRATA
                            for index in range(PER_STRATUM // 4))
        run_dir, _cases = _calibratable_run(root, holdout)
        prompt = c.prompt_sha256()
        before = report.judge_half(run_dir)
        if not before.problems:
            failures.append("прогон без разметки прочитан как откалиброванный — "
                            "проверка ни о чём")
        elif not any("размеченных" in one for one in before.problems):
            failures.append(f"отказ до разметки не называет её: {before.problems}")
        sheet = root / "sheet.jsonl"
        # БЕЗ --judge-model И БЕЗ --holdout: имя судьи берётся из meta.json
        # прогона, ярус — из лестницы. Оба забытых флага стоили бы трёхсот
        # размеченных вручную строк.
        code = _cli(["export", "--run", str(run_dir), "--out", str(sheet),
                     "--ladder", str(root / "ladder.json")])
        if code != 0:
            failures.append(f"export вернул {code}")
        rows = r.read_rows(sheet)
        if len(rows) != CALIBRATION.sample_size:
            failures.append(f"в листе {len(rows)} строк, спека просит "
                            f"{CALIBRATION.sample_size}")
        if any(row.get("judge_model") != MODEL for row in rows):
            failures.append("в листе не тот судья — умолчание из meta.json не сработало")
        if any(row.get("judge_label") for row in rows):
            failures.append("лист не слепой")
        drawn = sum(1 for row in rows if row.get("holdout"))
        wanted = int(round(len(rows) * CALIBRATION.holdout_share))
        if drawn < wanted:
            failures.append(f"holdout в листе {drawn}/{len(rows)}, квота §8.5 — {wanted}: "
                            f"ярус не доехал из лестницы")
        _fill_sheet(sheet, _human_label)
        extra = _script_the_repeats(run_dir, sheet, 5150)
        if extra != CALIBRATION.repeat_sample * (CALIBRATION.repeats - 1):
            failures.append(f"повторов судьи {extra}, спека просит "
                            f"{CALIBRATION.repeat_sample}×{CALIBRATION.repeats - 1}")
        code = _cli(["import", "--sheet", str(sheet), "--run", str(run_dir),
                     "--out", str(root / "calibration.jsonl")])
        if code != 0:
            failures.append(f"import вернул {code} — штамп не принят")
        after = report.judge_half(run_dir)
        if after.stamp is None:
            failures.append("штамп не лёг нулевой строкой в <run>.judge.jsonl")
        elif after.problems:
            failures.append(f"отчёт всё ещё считает судью некалиброванным: {after.problems}")
        elif after.stamp.n != CALIBRATION.sample_size:
            failures.append(f"в штампе {after.stamp.n} строк, размечено "
                            f"{CALIBRATION.sample_size}")
        # И ВЕРДИКТЫ ПРОГОНА НА МЕСТЕ: штамп — нулевая строка, а не замена файла.
        kept = sum(after.labels.values())
        if kept != len(STRATA) * PER_STRATUM - after.pregate:
            failures.append(f"штамп съел вердикты прогона: осталось {kept} из "
                            f"{len(STRATA) * PER_STRATUM}")
        # НЕГАТИВ: разметка наугад — тот же путь, и отчёт остаётся НЕПОЛНЫМ.
        random_sheet = root / "random.jsonl"
        random_sheet.write_text(sheet.read_text(encoding="utf-8"), encoding="utf-8")
        _fill_sheet(random_sheet,
                    lambda case_id: JUDGE_LABELS[_index_of(case_id) % len(JUDGE_LABELS)])
        c.repeats_path(random_sheet).write_text(
            c.repeats_path(sheet).read_text(encoding="utf-8"), encoding="utf-8")
        code = _cli(["import", "--sheet", str(random_sheet), "--run", str(run_dir),
                     "--out", str(root / "random-calibration.jsonl")])
        if code == 0:
            failures.append("разметка наугад принята как калибровка")
        refused = report.judge_half(run_dir)
        if not refused.problems:
            failures.append("после разметки наугад отчёт снова полный — "
                            "штамп пишется не из чисел")
        elif not any("κ" in one for one in refused.problems):
            failures.append(f"отказ не называет κ: {refused.problems}")
    return failures


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("sample_strata", test_sample_strata),
        ("repeats_never_duplicate_index_zero", test_repeats_never_duplicate_index_zero),
        ("kappa_known_values", test_kappa_known_values),
        ("repeat_check", test_repeat_check),
        ("thresholds", test_thresholds),
        ("recalibration_triggers", test_recalibration_triggers),
        ("import_refuses_bad_label", test_import_refuses_bad_label),
        ("sample_excludes_pregate_verdicts", test_sample_excludes_pregate_verdicts),
        ("sheet_is_blind", test_sheet_is_blind),
        ("repeats_are_real_judge_calls", test_repeats_are_real_judge_calls),
        ("import_joins_and_stamps_the_run", test_import_joins_and_stamps_the_run),
        ("minted_of_is_the_runs_own_list", test_minted_of_is_the_runs_own_list),
        ("the_sheet_shows_the_masked_dialogue", test_the_sheet_shows_the_masked_dialogue),
        ("the_whole_loop_runs_offline", test_the_whole_loop_runs_offline),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("calibration: PASS" if not failures else "calibration: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
