"""`report.py` pinned on a REAL run directory, written here from hand-built records.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_report

THE FIXTURE RUN IS WRITTEN, NOT MOCKED. `build_run` puts a v4-shaped
`corpus.json` and `<run>.arms.jsonl` on disk beside the v5 files, exactly as
`contracts.RUN_FILES` describes them, and the report is then produced by the
same code path a GO run uses — including `bench.agentpii4.autopsy._load_run`
and `bench.agentpii4.report.render`. The promise of §8 is that v4's own tools
read a v5 run directory unchanged, and only v4's code can testify to that.

The directory is built under `tempfile`, not committed: a fixture run in the
tree would be a second corpus to keep in step with `contracts.py`, and the one
thing it would prove — that the writers and the readers agree — is proved
better by writing it with the writers on every test run.
"""
import json
import sys
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from bench.agentpii4.records import ArmMeta, arm_record
from bench.agentpii5 import contracts, records
from bench.agentpii5.contracts import CalibrationStamp, JudgeVerdict, Line
from bench.agentpii5.fixtures import (
    FAKE_NAME,
    REAL_NAME,
    REAL_PHONE,
    _call,
    _case,
    _hop,
    _in_message,
    _item,
    _obs,
    _run,
    _seen,
    _with_calls,
    _with_mentions,
    _with_replies,
    _with_subs,
)
from bench.agentpii5.metrics import METRIC_FUNCTIONS, by_axis
from bench.agentpii5.observe import observe
from bench.agentpii5.report import (
    V4_BLOCK_END,
    V4_BLOCK_START,
    ReportError,
    differs_histogram,
    render_line,
    report_lines,
    run_id_of,
    v4_half,
    v5_observations,
)
from bench.agentpii5.schema import case_v5_to_json

RUN_ID = "fixture0001"
NAME = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(1, 0, len(REAL_NAME)))
PHONE = _item("p2", "PHONE", REAL_PHONE, REAL_PHONE, "i1", _in_message(1, 15, 27))
STAMP = CalibrationStamp(judge_model=contracts.JUDGE_MODEL, prompt_sha256="f" * 64, n=300,
                         raw_agreement=0.88, kappa=0.74, per_type_kappa={"NAME": 0.76},
                         repeat_disagreement=0.04, calibrated=True)


def _fixture_case():  # noqa: ANN202 - a CaseV5, named by its only caller
    in_user = _hop("IN", "user", "p1", 0, 1, "", -1, -1, "")
    out_arg = _hop("OUT", "tool_arg", "p1", 1, 1, "crm_upsert_contact", 0, -1, "contact.last_name")
    answer = _hop("OUT", "answer", "p1", 2, 1, "", -1, -1, "")
    return _case("c-0001", "single", ("ты оператор", f"{REAL_NAME}, {REAL_PHONE}"),
                 (NAME, PHONE), (in_user, out_arg, answer))


def _fixture_run(case):  # noqa: ANN001, ANN202 - an ArmRunV5 for that case
    run = _with_subs(_run("c-0001"), {"p1": FAKE_NAME})
    run = _with_replies(run, "Готово, ЩУКИН.", "Готово, Иванова.", "Готово, Иванова.")
    run = _with_calls(run, (_call("crm_upsert_contact", {"contact": {"last_name": "Пахомовой"}},
                                  {"contact": {"last_name": "Ивановой"}}, {}, "", 0),), (1,))
    return _with_mentions(run, (contracts.MentionRecord("p1", 1, -1, FAKE_NAME, 0),
                                contracts.MentionRecord("p1", 1, -1, FAKE_NAME, 1)))


def build_run(root: Path, run_id: str, with_v5: bool) -> Path:
    """One run directory on disk. `with_v5` False writes the v4 half only —
    that directory is the BASELINE, and a baseline carrying v5 files would be a
    baseline that had already moved with the treatment."""
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    case = _fixture_case()
    run = _fixture_run(case)
    meta = ArmMeta("fixture", 1, 0, "sess", "success", False, None, (), "", 0.0)
    (run_dir / "corpus.json").write_text(json.dumps(
        {"corpus": [case.base.to_json()], "digest": "digest-v4"}, ensure_ascii=False),
        encoding="utf-8")
    for arm in ("C", "I", "C2"):
        records.append_row(records.run_file(run_dir, run_id, "<run>.arms.jsonl"),
                           arm_record(replace(run.base, arm=arm), meta, case.base))
    if not with_v5:
        return run_dir
    (run_dir / "corpus.v5.json").write_text(json.dumps(
        {"corpus": [case_v5_to_json(case)], "digest": "digest-v5"}, ensure_ascii=False),
        encoding="utf-8")
    records.append_row(records.run_file(run_dir, run_id, "<run>.arms.v5.jsonl"),
                       records.arm_v5_record(run, meta, case.base))
    for hop in observe(case, run, None, None).hops:
        records.append_row(records.run_file(run_dir, run_id, "<run>.hops.jsonl"),
                           records.hop_observation_to_json(hop))
    judge = records.run_file(run_dir, run_id, "<run>.judge.jsonl")
    records.append_row(judge, records.calibration_stamp_to_json(STAMP))
    records.append_row(judge, records.judge_row_to_json(records.JudgeRow(
        case_id="c-0001", repeat=0, input_sha256="a" * 64,
        verdict=JudgeVerdict(label="верно", reason="«Иванова»", judged_by="model", cost_usd=0.01))))
    return run_dir


def _built(root: Path) -> tuple[Path, Path]:
    return build_run(root, RUN_ID, True), build_run(root, "baseline01", False)


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_run_dir_carries_the_agents_turns() -> list[str]:
    """Ruling R-40: the run directory is the only thing a `--report` replay and
    `calibration export` have, so the agent's per-turn replies must survive the
    write. A fixture run that stored none would make the judge's dialogue empty
    on every replay while the live run looked fine."""
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = build_run(Path(tmp), RUN_ID, True)
        rows = records.read_rows(records.run_file(run_dir, RUN_ID, "<run>.arms.v5.jsonl"))
        run = records.arm_v5_from_record(rows[0])
        if run.turn_replies != (run.base.reply,):
            failures.append(f"the written run lost the agent's turns: {run.turn_replies}")
        if any(FAKE_NAME in text for text in run.turn_replies):
            failures.append("a substitute survived into the agent's turns — "
                            "the judge reads these and must stay blind")
    return failures


def test_line_rendering() -> list[str]:
    """C-151. x/n, the rate, the exact interval — and what a flawless line
    CERTIFIES instead of «100%». A zero-total line is «н/п», never 0%."""
    problems: list[str] = []
    partial = render_line(Line("leak", 3, 4))
    if "3/4" not in partial or "75.00%" not in partial or "[" not in partial:
        problems.append(f"a partial line must show x/n, the rate and the interval: {partial!r}")
    perfect = render_line(Line("leak", 4, 4))
    if "сертифицирует" not in perfect:
        problems.append(f"a flawless line must certify a floor, not print 100%: {perfect!r}")
    if "100.00%" in perfect:
        problems.append("a finite sample printed 100%")
    empty = render_line(Line("leak", 0, 0))
    if "н/п" not in empty or "0.00%" in empty:
        problems.append(f"an empty line must be «н/п», never 0%: {empty!r}")
    return problems


def test_v4_block_byte_equal() -> list[str]:
    """C-066. The v4 half is v4's OWN output. A baseline re-typed here would
    drift from what v4's tools print, and a baseline that moves with the
    treatment measures nothing."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        lines = report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        own, _scored, _cases = v4_half(v5_dir, f"v5 run {run_id_of(v5_dir)}")
        start = lines.index(V4_BLOCK_START)
        end = lines.index(V4_BLOCK_END)
        block = lines[start:end]
        problems: list[str] = []
        for line in own:
            if line not in block:
                problems.append(f"v4's own line is missing from the block: {line!r}")
                break
        # The negative: a line v4 never printed must NOT be found by the same
        # search, or «is v4's text in there» would pass on any text at all.
        if "ВЕРДИКТ ЭКВИВАЛЕНТНОСТИ при δ=99pp" in block:
            problems.append("the containment check accepts text v4 never printed")
        return problems


def test_every_axis_prints() -> list[str]:
    """C-080. Every axis of `contracts.AXES` buckets the observations and every
    bucket renders. An axis that raised would silently drop a slice."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, _v4_dir = _built(Path(tmp))
        _block, scored, _cases = v4_half(v5_dir, "x")
        observations = v5_observations(v5_dir, scored)
        problems: list[str] = []
        for axis in contracts.AXES:
            buckets = by_axis(observations, axis)
            if not buckets:
                problems.append(f"{axis}: no buckets at all")
            for name, rows in buckets.items():
                if not render_line(METRIC_FUNCTIONS["form_hOUT"](rows)):
                    problems.append(f"{axis}/{name}: rendered nothing")
        return problems


def test_differs_histogram() -> list[str]:
    """C-181. Per feature, how many hops named it. The report says «падеж и
    регистр»; a bare «нет» sends nobody anywhere."""
    case = _fixture_case()
    hop = case.hops[1]
    shouted = _obs(case, _run("c-0001"), (_seen(case, hop, "NAME", "ОРЛОВ ИВАН", "Орлов Иван"),))
    counts = differs_histogram((shouted,), "NAME")
    problems: list[str] = []
    if counts.get("case_class") != 1:
        problems.append(f"case_class should be counted once: {counts}")
    if sum(counts.values()) != 1:
        problems.append(f"only the features in `differs` are counted: {counts}")
    exact = _obs(case, _run("c-0001"), (_seen(case, hop, "NAME", "Орлов Иван", "Орлов Иван"),))
    if sum(differs_histogram((exact,), "NAME").values()) != 0:
        problems.append("a matching hop contributed to the histogram")
    try:
        differs_histogram((shouted,), "ОРГАНИЗАЦИЯ")
        problems.append("a type with no features was accepted")
    except ReportError:
        pass
    return problems


def test_leak_and_coverage_both_present() -> list[str]:
    """C-092. Overlap is not coverage and the two numbers are never merged:
    97.6% recall beside 95.0% coverage is 69 partial leaks the single number
    hid, and a report that prints one of them prints half the instrument."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        lines = report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        leak = [one for one in lines if one.strip().startswith("leak ")]
        coverage = [one for one in lines if one.strip().startswith("coverage ")]
        problems: list[str] = []
        if len(leak) != 1 or len(coverage) != 1:
            problems.append(f"expected one line each, got leak={len(leak)} coverage={len(coverage)}")
        if leak and coverage and leak[0] == coverage[0]:
            problems.append("leak and coverage rendered as one line")
        return problems


def _equivalence_outside(lines: list[str]) -> list[str]:
    start, end = lines.index(V4_BLOCK_START), lines.index(V4_BLOCK_END)
    return [one for index, one in enumerate(lines)
            if "эквивалент" in one.casefold() and not start < index < end]


def test_no_effect_claims_outside_v4_block() -> list[str]:
    """C-095. «No effect» is a claim about a DIFFERENCE and only TOST at δ=3pp
    earns it. The v5 lines are absolute rates; the word belongs to v4's block
    and to nothing else."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        lines = report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        problems: list[str] = []
        stray = _equivalence_outside(lines)
        if stray:
            problems.append(f"«эквивалентно» outside the v4 block: {stray}")
        # The negative fixture: the same checker must CATCH a claim planted
        # after the block, or the check above is a check on the empty set.
        planted = lines + ["   форма эквивалентна контролю"]
        if not _equivalence_outside(planted):
            problems.append("the checker does not notice a claim planted outside the block")
        return problems


def test_side_by_side_sections() -> list[str]:
    """C-190. The v4 block precedes the v5 lines, both halves name their run,
    and every section the brief fixes is present in its order."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        lines = report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        text = "\n".join(lines)
        problems: list[str] = []
        order = [V4_BLOCK_START, V4_BLOCK_END, "2. ЛИНИИ v5", "3. ФОРМА",
                 "4. ЧУВСТВИТЕЛЬНОСТЬ", "5. СУДЬЯ", "6. ОТКАЗЫ ГЕЙТА", "7. ПРИМЕРЫ"]
        found = [text.find(marker) for marker in order]
        if -1 in found:
            problems.append(f"missing sections: {[order[i] for i, at in enumerate(found) if at < 0]}")
        elif found != sorted(found):
            problems.append(f"sections out of order: {order}")
        if str(v5_dir) not in lines[0] or str(v4_dir) not in lines[0]:
            problems.append(f"the header names neither run: {lines[0]!r}")
        if contracts.INCOMPLETE_REPORT_MARK in lines[0]:
            problems.append("a complete run was marked НЕПОЛНЫЙ")
        for name in ("<run>.report.txt", "<run>.gate.json"):
            if not records.run_file(v5_dir, run_id_of(v5_dir), name).exists():
                problems.append(f"{name} was not written")
        return problems


def test_baseline_without_v5_files_is_refused() -> list[str]:
    """A v5 report needs the v5 corpus. Asked for one on a v4-only directory it
    must say so, not quietly report on nothing."""
    with tempfile.TemporaryDirectory() as tmp:
        _v5_dir, v4_dir = _built(Path(tmp))
        try:
            report_lines(v4_dir, v4_dir, METRIC_FUNCTIONS)
        except ReportError as error:
            return [] if "corpus.v5.json" in str(error) else [f"unclear refusal: {error}"]
        return ["a v4-only directory was reported on as a v5 run"]


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("run_dir_carries_the_agents_turns", test_run_dir_carries_the_agents_turns),
        ("line_rendering", test_line_rendering),
        ("v4_block_byte_equal", test_v4_block_byte_equal),
        ("every_axis_prints", test_every_axis_prints),
        ("differs_histogram", test_differs_histogram),
        ("leak_and_coverage_both_present", test_leak_and_coverage_both_present),
        ("no_effect_claims_outside_v4_block", test_no_effect_claims_outside_v4_block),
        ("side_by_side_sections", test_side_by_side_sections),
        ("baseline_without_v5_files_is_refused", test_baseline_without_v5_files_is_refused),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("report: PASS" if not failures else "report: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
