"""КАЛИБРОВКА СУДЬИ — согласие с человеком, и отказ от отчёта без него.

Spec §8.5: 300 answers stratified by PII type × family × register, ≥ 20 per
stratum where there are that many, 20% of them from the holdout tier; labelled
by hand on one scale (`JUDGE_LABELS`); the judge is fit when raw agreement
≥ 0.85 AND κ ≥ 0.70 on the whole sample and on every type with ≥ 20 examples,
and when K=3 repeats on 50 answers disagree on ≤ 10% of them.

THREE THINGS MAKE THIS AN INSTRUMENT RATHER THAN A CERTIFICATE.

1. **A `none` verdict counts as a DISAGREEMENT, it is not dropped.** Dropping
   it would let a judge that answers «нет счётного вердикта» to everything
   calibrate on an empty denominator — perfect agreement over nothing.
2. **κ is 0.0 when a rater is constant.** Cohen's κ is undefined there
   (`pe == 1`), and the two readings are «certify it» or «refuse it»: a judge
   that always says «верно» on a corpus that is mostly «верно» has demonstrated
   nothing, so it is refused.
3. **A missing stability sub-sample is 1.0 disagreement, not 0.0.** The
   question was not asked; that is not «stable», and one number says so on the
   report's own line.

`stamp()` counts ONLY the rows whose `judge_model` and `prompt_sha256` equal
the ones it is asked about, so a prompt edit invalidates a calibration
mechanically rather than by somebody remembering to.

No `pseudex` here (`contracts.PSEUDEX_ALLOWED_MODULES`), and no model call: the
judge's verdicts are read off `<run>.judge.jsonl`, the human's off the sheet.
"""
import argparse
import json
import random
import sys
from collections.abc import Sequence
from pathlib import Path

from bench.agentpii5 import records as r
from bench.agentpii5.contracts import (
    CALIBRATION, JUDGE_LABELS, CalibrationRecord, CalibrationStamp,
    CalibrationThresholds, RunObservation)
from bench.agentpii5.judge import judge_input, prompt_sha256
from bench.agentpii5.schema import case_v5_from_json

# Where a calibration file lives, derived from `contracts.CALIBRATION_FILE`
# rather than restated: the template is the contract and a second spelling of
# it is a file the report would never find.
CALIBRATION_DIR: str = "bench/agentpii5/calibration"
# The label a judge row carries when no quote stood. It is a value of
# `CalibrationRecord.judge_label` and never of `human_label`.
NO_VERDICT: str = "none"


class CalibrationError(ValueError):
    """A calibration that cannot be computed, named by what is missing.

    Never a 0.0 in its place: a metric that returns a number on absent data is
    the v4 defect class this benchmark exists to avoid.
    """


def calibration_path(root: Path, judge_model: str, prompt_hash: str) -> Path:
    """`bench/agentpii5/calibration/<judge_model>.<prompt_sha256[:12]>.jsonl`."""
    return root / CALIBRATION_DIR / f"{judge_model}.{prompt_hash[:12]}.jsonl"


# --- the sample -----------------------------------------------------------------------

def answer_types(observation: RunObservation) -> tuple[str, ...]:
    """The PII types the ANSWER carried — the stratum axis the spec names.

    Read off the OUT/answer hops, not off the case's items: the judge is asked
    about the answer, and a case whose personal data never reached the answer
    teaches the calibration nothing about any type.
    """
    return tuple(sorted({hop.pii_type for hop in observation.hops
                         if hop.hop.kind == "OUT" and hop.hop.owner == "answer"}))


def stratum_of(observation: RunObservation) -> tuple[str, str, str]:
    return ("+".join(answer_types(observation)), observation.case.behaviour,
            observation.case.base.register)


def draw_sample(observations: Sequence[RunObservation], thresholds: CalibrationThresholds,
                seed: int, holdout_ids: frozenset[str]) -> tuple[CalibrationRecord, ...]:
    """The labelling sample: `sample_size` rows, stratified, holdout-quota met.

    `holdout_ids` IS A FOURTH ARGUMENT AND HAS TO BE. The tier lives in the
    ladder (`bench/agentpii5/ladder.json`), never on the case, so a
    `holdout` flag derived from an observation alone would be False on every
    row and the 20% rule would silently never hold — a threshold that cannot
    fail. The caller passes `tier(cases, ladder, "holdout")`.

    Allocation: `per_stratum_min` per stratum where the stratum has that many,
    then the remainder by largest remainder on the leftover capacity. The
    holdout quota is met by SWAPPING picked non-holdout rows for unpicked
    holdout rows of the same stratum, so the strata counts stay exactly as
    allocated and the quota does not quietly rewrite the stratification.
    """
    eligible = [one for one in observations if answer_types(one)]
    if not eligible:
        raise CalibrationError(
            "ни один ответ прогона не нёс персональных данных: калибровать "
            "судью не на чем (страта — тип ПД × семья × регистр)")
    rng = random.Random(seed)
    strata: dict[tuple[str, str, str], list[RunObservation]] = {}
    for one in eligible:
        strata.setdefault(stratum_of(one), []).append(one)
    for rows in strata.values():
        rows.sort(key=lambda one: (one.case.base.id, one.repeat))
        rng.shuffle(rows)
    picked = _allocate(strata, thresholds.sample_size, thresholds.per_stratum_min)
    picked = _meet_holdout(strata, picked, holdout_ids, thresholds.holdout_share)
    out: list[CalibrationRecord] = []
    for stratum in sorted(picked):
        for one in picked[stratum]:
            out.append(_record(one, holdout_ids, 0))
    return tuple(out)


def _allocate(strata: dict[tuple[str, str, str], list[RunObservation]], size: int,
              per_stratum_min: int) -> dict[tuple[str, str, str], list[RunObservation]]:
    counts = {name: min(per_stratum_min, len(rows)) for name, rows in strata.items()}
    taken = sum(counts.values())
    spare = {name: len(rows) - counts[name] for name, rows in strata.items()}
    remaining = size - taken
    if remaining < 0:
        # More strata than the sample can hold at the floor: drop from the
        # largest strata first, so a rare type keeps its examples.
        for name in sorted(counts, key=lambda one: (-counts[one], one)):
            while remaining < 0 and counts[name] > 1:
                counts[name] -= 1
                remaining += 1
    while remaining > 0 and any(spare.values()):
        share = {name: len(rows) for name, rows in strata.items() if spare[name] > 0}
        total = sum(share.values())
        given = 0
        order = sorted(share, key=lambda one: (-share[one], one))
        for name in order:
            extra = min(spare[name], max(1, (share[name] * remaining) // total))
            extra = min(extra, remaining - given)
            counts[name] += extra
            spare[name] -= extra
            given += extra
            if given == remaining:
                break
        if given == 0:
            break
        remaining -= given
    return {name: strata[name][:counts[name]] for name in sorted(strata)}


def _meet_holdout(strata: dict[tuple[str, str, str], list[RunObservation]],
                  picked: dict[tuple[str, str, str], list[RunObservation]],
                  holdout_ids: frozenset[str], share: float,
                  ) -> dict[tuple[str, str, str], list[RunObservation]]:
    wanted = int(round(sum(len(rows) for rows in picked.values()) * share))
    have = sum(1 for rows in picked.values() for one in rows if one.case.base.id in holdout_ids)
    out = {name: list(rows) for name, rows in picked.items()}
    for name in sorted(out):
        if have >= wanted:
            break
        chosen = {(one.case.base.id, one.repeat) for one in out[name]}
        spare = [one for one in strata[name]
                 if (one.case.base.id, one.repeat) not in chosen and one.case.base.id in holdout_ids]
        for index, one in enumerate(out[name]):
            if have >= wanted or not spare:
                break
            if one.case.base.id in holdout_ids:
                continue
            out[name][index] = spare.pop()
            have += 1
    return out


def _record(observation: RunObservation, holdout_ids: frozenset[str],
            repeat_index: int) -> CalibrationRecord:
    return CalibrationRecord(
        sample_id=f"{observation.case.base.id}|{observation.repeat}",
        case_id=observation.case.base.id, pii_types=answer_types(observation),
        family=observation.case.behaviour, register=observation.case.base.register,
        holdout=observation.case.base.id in holdout_ids, human_label="", judge_label="",
        judge_reason="", repeat_index=repeat_index, judge_model="", prompt_sha256="")


def draw_repeats(sample: Sequence[CalibrationRecord], thresholds: CalibrationThresholds,
                 seed: int) -> tuple[CalibrationRecord, ...]:
    """The stability sub-sample: the EXTRA rows of `repeat_sample` answers.

    `repeat_index` 1..K-1, never 0: the drawn sample already holds each answer
    once at index 0, and emitting a second index-0 row would duplicate it in
    `labelled()` — fifty answers counted twice in the agreement they are not
    about.
    """
    rows = sorted(sample, key=lambda one: one.sample_id)
    rng = random.Random(seed)
    rng.shuffle(rows)
    out: list[CalibrationRecord] = []
    for one in rows[:thresholds.repeat_sample]:
        for index in range(1, thresholds.repeats):
            out.append(CalibrationRecord(
                sample_id=one.sample_id, case_id=one.case_id, pii_types=one.pii_types,
                family=one.family, register=one.register, holdout=one.holdout,
                human_label=one.human_label, judge_label=one.judge_label,
                judge_reason=one.judge_reason, repeat_index=index,
                judge_model=one.judge_model, prompt_sha256=one.prompt_sha256))
    return tuple(out)


# --- the numbers ----------------------------------------------------------------------

def labelled(records: Sequence[CalibrationRecord]) -> tuple[CalibrationRecord, ...]:
    """Rows a human has labelled, one row per answer (`repeat_index == 0`).

    The repeats belong to `repeat_check` alone: counting all three copies of one
    answer in the agreement would weight fifty answers three times against the
    other two hundred and fifty.
    """
    return tuple(one for one in records if one.human_label and one.repeat_index == 0)


def agreement(records: Sequence[CalibrationRecord]) -> float:
    """Raw agreement. A `none` judge label is a disagreement, not an exclusion."""
    rows = labelled(records)
    if not rows:
        raise CalibrationError("в выборке нет ни одной размеченной человеком строки")
    return sum(1 for one in rows if one.judge_label == one.human_label) / len(rows)


def kappa(records: Sequence[CalibrationRecord]) -> float:
    """Cohen's κ over the four labels plus `none`, implemented here.

    No sklearn: the whole computation is six lines, and a dependency in an
    instrument is a version that can move a published number.
    """
    rows = labelled(records)
    if not rows:
        raise CalibrationError("в выборке нет ни одной размеченной человеком строки")
    total = len(rows)
    categories = sorted({one.human_label for one in rows} | {one.judge_label for one in rows})
    observed = sum(1 for one in rows if one.judge_label == one.human_label) / total
    expected = sum((sum(1 for one in rows if one.human_label == name) / total)
                   * (sum(1 for one in rows if one.judge_label == name) / total)
                   for name in categories)
    if expected >= 1.0:
        # One rater was constant: κ is undefined, and certifying it would pass a
        # judge that always says the same word on a corpus that mostly is.
        return 0.0
    return (observed - expected) / (1.0 - expected)


def per_type_kappa(records: Sequence[CalibrationRecord],
                   thresholds: CalibrationThresholds) -> dict[str, float]:
    """κ per PII type, for the types with enough examples to mean anything."""
    rows = labelled(records)
    by_type: dict[str, list[CalibrationRecord]] = {}
    for one in rows:
        for pii_type in one.pii_types:
            by_type.setdefault(pii_type, []).append(one)
    return {name: kappa(subset) for name, subset in sorted(by_type.items())
            if len(subset) >= thresholds.per_type_min_examples}


def has_repeats(records: Sequence[CalibrationRecord]) -> bool:
    groups: dict[str, int] = {}
    for one in records:
        groups[one.sample_id] = groups.get(one.sample_id, 0) + 1
    return any(count >= 2 for count in groups.values())


def repeat_check(records: Sequence[CalibrationRecord]) -> float:
    """Share of answers whose K judge labels are NOT all equal."""
    groups: dict[str, list[str]] = {}
    for one in records:
        groups.setdefault(one.sample_id, []).append(one.judge_label)
    repeated = {name: labels for name, labels in groups.items() if len(labels) >= 2}
    if not repeated:
        raise CalibrationError(
            "в выборке нет подвыборки на устойчивость (K повторов одного ответа): "
            "спред судьи не спрашивали")
    return sum(1 for labels in repeated.values() if len(set(labels)) > 1) / len(repeated)


def stamp(records: Sequence[CalibrationRecord], judge_model: str,
          prompt_hash: str) -> CalibrationStamp:
    """What a report prints about the judge it used.

    Only rows of THIS model and THIS prompt count: a calibration inherited from
    another prompt is not a calibration of the judge that ran.
    """
    mine = [one for one in records
            if one.judge_model == judge_model and one.prompt_sha256 == prompt_hash]
    rows = labelled(mine)
    if not rows:
        return CalibrationStamp(judge_model=judge_model, prompt_sha256=prompt_hash, n=0,
                                raw_agreement=0.0, kappa=0.0, per_type_kappa={},
                                repeat_disagreement=1.0, calibrated=False)
    raw = agreement(mine)
    whole = kappa(mine)
    per_type = per_type_kappa(mine, CALIBRATION)
    # No sub-sample means the stability question was never asked; that is not
    # «stable», and 1.0 says so in the same number the threshold reads.
    spread = repeat_check(mine) if has_repeats(mine) else 1.0
    calibrated = (len(rows) >= CALIBRATION.sample_size
                  and raw >= CALIBRATION.raw_agreement_min
                  and whole >= CALIBRATION.kappa_min
                  and all(value >= CALIBRATION.kappa_min for value in per_type.values())
                  and spread <= CALIBRATION.max_repeat_disagreement)
    return CalibrationStamp(judge_model=judge_model, prompt_sha256=prompt_hash, n=len(rows),
                            raw_agreement=raw, kappa=whole, per_type_kappa=per_type,
                            repeat_disagreement=spread, calibrated=calibrated)


def is_current(calibration: CalibrationStamp, judge_model: str, prompt_hash: str,
               corpus_digest: str, previous_digest: str, changed_share: float) -> bool:
    """Whether this stamp still describes the judge that is about to run.

    False on a different model, a different prompt, an uncalibrated stamp, or a
    corpus that moved by `recalibrate_on_corpus_change` or more (spec §8.5).
    """
    if not calibration.calibrated:
        return False
    if calibration.judge_model != judge_model or calibration.prompt_sha256 != prompt_hash:
        return False
    if corpus_digest != previous_digest and changed_share >= CALIBRATION.recalibrate_on_corpus_change:
        return False
    return True


# --- reading a run, and the sheet -----------------------------------------------------

def observations_of(run_dir: Path) -> list[RunObservation]:
    """The `RunObservation`s of a run, from FILES, with no v4 scoring.

    `report.v5_observations` does the same and additionally joins the v4 paired
    verdicts, which needs v4's whole scoring pass; a labelling sheet needs the
    hops and the case and nothing else, so `ic`/`cc` stay None here.
    """
    run_id = _run_id(run_dir)
    corpus = run_dir / "corpus.v5.json"
    if not corpus.exists():
        raise CalibrationError(f"{run_dir}: нет corpus.v5.json — выборку не из чего строить")
    cases = {one.base.id: one for one in
             (case_v5_from_json(row) for row in
              json.loads(corpus.read_text(encoding="utf-8"))["corpus"])}
    hops: dict[tuple[str, int], list[object]] = {}
    hops_path = r.run_file(run_dir, run_id, "<run>.hops.jsonl")
    for row in r.read_rows(hops_path) if hops_path.exists() else []:
        one = r.hop_observation_from_json(row)
        hops.setdefault((one.case_id, one.repeat), []).append(one)
    out: list[RunObservation] = []
    for row in r.merged_v5_records(run_dir):
        run = r.arm_v5_from_record(row)
        case = cases.get(run.base.case_id)
        if case is None:
            raise CalibrationError(
                f"{run_dir}: плечо {run.base.case_id!r} без случая в corpus.v5.json")
        out.append(RunObservation(
            case=case, repeat=run.base.repeat,
            hops=tuple(hops.get((run.base.case_id, run.base.repeat), ())),  # type: ignore[arg-type]
            run=run, ic=None, cc=None))
    return out


def _run_id(run_dir: Path) -> str:
    found = sorted(run_dir.glob("*.arms.jsonl"))
    if not found:
        raise CalibrationError(f"{run_dir}: нет <run>.arms.jsonl — это не каталог прогона")
    return found[0].name[: -len(".arms.jsonl")]


def judge_labels_of(run_dir: Path) -> dict[tuple[str, int], tuple[str, str]]:
    """(case, repeat) → (label, reason) from `<run>.judge.jsonl`."""
    run_id = _run_id(run_dir)
    path = r.run_file(run_dir, run_id, "<run>.judge.jsonl")
    if not path.exists():
        return {}
    out: dict[tuple[str, int], tuple[str, str]] = {}
    for row in r.read_rows(path):
        if "calibrated" in row:      # the stamp `report.judge_half` reads first
            continue
        one = r.judge_row_from_json(row)
        out[(one.case_id, one.repeat)] = (one.verdict.label or NO_VERDICT, one.verdict.reason)
    return out


def sheet_rows(run_dir: Path, sample: Sequence[CalibrationRecord],
               judge_model: str) -> list[dict[str, object]]:
    """The labelling sheet: the calibration row PLUS what the judge saw.

    The extra keys are not part of `CalibrationRecord` and are dropped on
    import: the labeller needs the answer, the oracle and the dialogue in front
    of them, and a record that carried them would put the customer's values
    into the calibration file for ever.

    THE SHEET IS BUILT BY `judge_input`, NOT BESIDE IT. κ measures a human
    against the judge, so the two must have read the SAME thing — including the
    agent's own earlier turns (`ArmRunV5.turn_replies`, ruling R-40), which
    reach the sheet because they reach `dialogue_context`. A second builder
    here would be a second thing to keep equal, and the first divergence would
    be a κ nobody could explain.
    """
    verdicts = judge_labels_of(run_dir)
    runs = {(one.case.base.id, one.repeat): one for one in observations_of(run_dir)}
    out: list[dict[str, object]] = []
    for record in sample:
        case_id, repeat = record.sample_id.split("|")
        observation = runs.get((case_id, int(repeat)))
        if observation is None:
            raise CalibrationError(f"{record.sample_id}: строки выборки нет в прогоне {run_dir}")
        label, reason = verdicts.get((case_id, int(repeat)), ("", ""))
        request = judge_input(observation.case, observation.run)
        row = r.calibration_record_to_json(CalibrationRecord(
            sample_id=record.sample_id, case_id=record.case_id, pii_types=record.pii_types,
            family=record.family, register=record.register, holdout=record.holdout,
            human_label="", judge_label=label, judge_reason=reason,
            repeat_index=record.repeat_index, judge_model=judge_model,
            prompt_sha256=prompt_sha256()))
        row["restored_answer"] = request.restored_answer
        row["oracle_literals"] = list(request.oracle_literals)
        row["dialogue_context"] = [{"role": turn.role, "text": turn.text}
                                   for turn in request.dialogue_context]
        row["customer_question"] = request.customer_question
        out.append(row)
    return out


def read_sheet(path: Path) -> tuple[CalibrationRecord, ...]:
    """A filled sheet as records. A row whose human label is not one of
    `JUDGE_LABELS` stops the import by name — an unreadable label silently
    dropped is a sample size nobody can reconstruct."""
    out: list[CalibrationRecord] = []
    for number, row in enumerate(r.read_rows(path), start=1):
        human = row.get("human_label")
        if human not in JUDGE_LABELS:
            raise CalibrationError(
                f"{path}:{number}: human_label={human!r} — разметка ведётся по "
                f"{JUDGE_LABELS}, пустых и своих меток в файле калибровки нет")
        out.append(r.calibration_record_from_json(
            {key: value for key, value in row.items()
             if key in ("sample_id", "case_id", "pii_types", "family", "register", "holdout",
                        "human_label", "judge_label", "judge_reason", "repeat_index",
                        "judge_model", "prompt_sha256")}))
    return tuple(out)


# --- CLI -------------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export", help="лист разметки из прогона")
    export.add_argument("--run", required=True, type=Path)
    export.add_argument("--out", required=True, type=Path)
    export.add_argument("--seed", type=int, default=5150)
    export.add_argument("--judge-model", default="")
    export.add_argument("--holdout", default="", help="запятые: id случаев яруса holdout")

    load = sub.add_parser("import", help="размеченный лист -> файл калибровки")
    load.add_argument("--sheet", required=True, type=Path)
    load.add_argument("--out", required=True, type=Path)

    show = sub.add_parser("stamp", help="штамп по файлу калибровки; код 1, если не откалиброван")
    show.add_argument("--file", required=True, type=Path)
    show.add_argument("--judge-model", default="")

    args = parser.parse_args()
    if args.command == "export":
        holdout = frozenset(one.strip() for one in args.holdout.split(",") if one.strip())
        sample = draw_sample(observations_of(args.run), CALIBRATION, args.seed, holdout)
        rows = sheet_rows(args.run, sample, args.judge_model)
        rows += sheet_rows(args.run, draw_repeats(sample, CALIBRATION, args.seed), args.judge_model)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                                    for row in rows), encoding="utf-8")
        print(f"лист разметки: {args.out} · строк {len(rows)} · "
              f"промпт {prompt_sha256()[:12]}")
        return 0
    if args.command == "import":
        parsed = read_sheet(args.sheet)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text("".join(
            json.dumps(r.calibration_record_to_json(one), ensure_ascii=False, sort_keys=True) + "\n"
            for one in parsed), encoding="utf-8")
        print(f"калибровка: {args.out} · строк {len(parsed)}")
        return 0
    parsed = tuple(r.calibration_record_from_json(row) for row in r.read_rows(args.file))
    model = args.judge_model or (parsed[0].judge_model if parsed else "")
    result = stamp(parsed, model, prompt_sha256())
    print(json.dumps(r.calibration_stamp_to_json(result), ensure_ascii=False, indent=2))
    if not result.calibrated:
        print("СУДЬЯ НЕ ОТКАЛИБРОВАН — отчёт с ним внутри не публикуется", file=sys.stderr)
    return 0 if result.calibrated else 1


if __name__ == "__main__":
    raise SystemExit(main())
