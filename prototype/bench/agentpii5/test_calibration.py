"""`calibration.py` pinned: the strata, the thresholds, κ on a textbook table.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_calibration

Offline, no model. The thresholds are checked from BOTH sides — a sample that
must calibrate and a sample that must not — because a `calibrated` that is
True on everything is a certificate, and the spec's whole point is that an
uncalibrated judge stops a report.
"""
import sys
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from bench.agentpii5 import calibration as c
from bench.agentpii5 import records as r
from bench.agentpii5.contracts import (
    CALIBRATION, CalibrationRecord, CalibrationStamp, HopObservation, RunObservation)
from bench.agentpii5.fixtures import NAME_ITEM, PHONE_ITEM, _case, _hop, _run

MODEL: str = "claude-sonnet-5"
PROMPT: str = "a" * 64


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
    """K-1 more rows per answer for the stability sub-sample."""
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
    sample = c.draw_sample(population, thresholds, 5150, holdout)
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
    if c.draw_sample(population, thresholds, 5150, holdout) != sample:
        failures.append("та же выборка при том же зерне вышла другой")
    if c.draw_sample(population, thresholds, 6060, holdout) == sample:
        failures.append("другое зерно дало ту же выборку — зерно ни на что не влияет")
    # The NEGATIVE: answers with no personal data cannot be stratified by type.
    empty = [replace(one, hops=()) for one in population]
    try:
        c.draw_sample(empty, thresholds, 5150, frozenset())
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
    sample = c.draw_sample(_population(), thresholds, 5150, frozenset())
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
    rows = _records(2, "NAME", 2, "верно", "неверно", "sheet")
    with tempfile.TemporaryDirectory() as tmp:
        sheet = Path(tmp) / "sheet.jsonl"
        for one in rows:
            row = r.calibration_record_to_json(one)
            row["restored_answer"] = "курьер приедет"          # dropped on import
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
