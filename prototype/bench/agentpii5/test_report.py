"""`report.py` pinned on a REAL run directory, written here from hand-built records.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_report

THE FIXTURE RUN IS WRITTEN, NOT MOCKED. `build_run` puts a v4-shaped
`corpus.json` and `<run>.arms.jsonl` on disk beside the v5 files, exactly as
`contracts.RUN_FILES` describes them — and, since the phase-4 review, the three
files the report's own sections are computed from as well (`<run>.triples.
jsonl`, `<run>.spend.tsv`, `<run>.meta.json`). The report is then produced by
the same code path a GO run uses — including `bench.agentpii4.autopsy._load_run`
and `bench.agentpii4.report.render`. The promise of §8 is that v4's own tools
read a v5 run directory unchanged, and only v4's code can testify to that.

The directory is built under `tempfile`, not committed: a fixture run in the
tree would be a second corpus to keep in step with `contracts.py`, and the one
thing it would prove — that the writers and the readers agree — is proved
better by writing it with the writers on every test run.

FOUR CHECKS HERE ARE THE REVIEWERS' OWN REPRODUCTIONS, turned into tests that
go red the moment the fix is reverted: the level table that could only show
agreement (#6), the hops file whose absence certified cleanliness (#5), the
calibration stamp that was believed (#7), and the price that was never printed
(G-cost). Each one asserts the defect's shape, not merely the fix's presence.
"""
import json
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from bench.agentpii4.records import ArmMeta, arm_record
from bench.agentpii5 import contracts, records
from bench.agentpii5.contracts import CalibrationStamp, CaseV5, JudgeVerdict, Line
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
from bench.agentpii5.metrics import AXIS_NOTE, METRIC_FUNCTIONS, prints_on_axis
from bench.agentpii5.observe import observe
from bench.agentpii5.report import (
    BESIDE,
    V4_BLOCK_END,
    V4_BLOCK_START,
    ReportError,
    calibration_problems,
    cost_lines,
    differs_histogram,
    level_rows,
    read_parts,
    render_line,
    report_lines,
    run_id_of,
    side_by_side,
    v4_half,
    v5_observations,
)
from bench.agentpii5.schema import case_v5_to_json

RUN_ID = "fixture0001"
PROMPT_SHA = "f" * 64
CEILING_USD = 12.0
NAME = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(1, 0, len(REAL_NAME)))
PHONE = _item("p2", "PHONE", REAL_PHONE, REAL_PHONE, "i1", _in_message(1, 15, 27))
STAMP = CalibrationStamp(judge_model=contracts.JUDGE_MODEL, prompt_sha256=PROMPT_SHA, n=300,
                         raw_agreement=0.88, kappa=0.74, per_type_kappa={"NAME": 0.76},
                         repeat_disagreement=0.04, calibrated=True)


def _fixture_case(case_id: str, behaviour: str) -> CaseV5:
    in_user = _hop("IN", "user", "p1", 0, 1, "", -1, -1, "")
    out_arg = _hop("OUT", "tool_arg", "p1", 1, 1, "crm_upsert_contact", 0, -1, "contact.last_name")
    answer = _hop("OUT", "answer", "p1", 2, 1, "", -1, -1, "")
    return _case(case_id, behaviour, ("ты оператор", f"{REAL_NAME}, {REAL_PHONE}"),
                 (NAME, PHONE), (in_user, out_arg, answer))


def _fixture_run(case: CaseV5):  # noqa: ANN202 - an ArmRunV5 for that case
    run = _with_subs(_run(case.base.id), {"p1": FAKE_NAME})
    run = _with_replies(run, "Готово, ЩУКИН.", "Готово, Иванова.", "Готово, Иванова.")
    run = _with_calls(run, (_call("crm_upsert_contact", {"contact": {"last_name": "Пахомовой"}},
                                  {"contact": {"last_name": "Ивановой"}}, {}, "", 0),), (1,))
    return _with_mentions(run, (contracts.MentionRecord("p1", 1, -1, FAKE_NAME, 0),
                                contracts.MentionRecord("p1", 1, -1, FAKE_NAME, 1)))


# TWO behaviours, because the per-behaviour v4 blocks (C-043/C-046/C-047) are a
# claim about EACH family: a fixture with one behaviour cannot tell «one block
# per behaviour» from «one block».
FIXTURE_BEHAVIOURS: tuple[tuple[str, str], ...] = (
    ("c-0001", "single"), ("c-0002", "retry_same_tool"))


JUDGE_USD = 0.01


def _triple_row(case: CaseV5) -> dict[str, object]:
    """One `<run>.triples.jsonl` row in the shape `harness.run_triple_v5`
    writes: the cost section is computed from these fields and from nothing
    else, so a fixture that invented its own shape would pin the wrong file.

    The two totals are written through `records.triple_totals_to_json` and not
    as literals here (F2.12 / R-54): the report reads them through that
    module's reader, and a fixture that spelled the keys itself would go on
    passing the day the writer renamed one."""
    return {"case_id": case.base.id, "repeat": 0, "kind": case.base.kind,
            "behaviour": case.behaviour, "register": case.base.register,
            "cluster": case.base.cluster, "cap_usd": 0.06, "cost_usd": 0.12,
            "status": "complete", "reason": "",
            "arms": {arm: {"termination": "done", "cost_usd": 0.04, "calls": 1, "reason": ""}
                     for arm in ("C", "I", "C2")},
            "judge": {"label": "верно", "judged_by": "model", "cost_usd": JUDGE_USD},
            **records.triple_totals_to_json(
                records.TripleTotals(judge_cost_usd=JUDGE_USD, turn_residual=0))}


def build_run(root: Path, run_id: str, with_v5: bool) -> Path:
    """One run directory on disk. `with_v5` False writes the v4 half only —
    that directory is the BASELINE, and a baseline carrying v5 files would be a
    baseline that had already moved with the treatment."""
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cases = [_fixture_case(case_id, behaviour) for case_id, behaviour in FIXTURE_BEHAVIOURS]
    meta = ArmMeta("fixture", 1, 0, "sess", "success", False, None, (), "", 0.0)
    (run_dir / "corpus.json").write_text(json.dumps(
        {"corpus": [case.base.to_json() for case in cases], "digest": "digest-v4"},
        ensure_ascii=False), encoding="utf-8")
    for case in cases:
        run = _fixture_run(case)
        for arm in ("C", "I", "C2"):
            records.append_row(records.run_file(run_dir, run_id, "<run>.arms.jsonl"),
                               arm_record(replace(run.base, arm=arm), meta, case.base))
    if not with_v5:
        return run_dir
    (run_dir / "corpus.v5.json").write_text(json.dumps(
        {"corpus": [case_v5_to_json(case) for case in cases], "digest": "digest-v5"},
        ensure_ascii=False), encoding="utf-8")
    judge = records.run_file(run_dir, run_id, "<run>.judge.jsonl")
    records.append_row(judge, records.calibration_stamp_to_json(STAMP))
    spend = 0.0
    for case in cases:
        run = _fixture_run(case)
        records.append_row(records.run_file(run_dir, run_id, "<run>.arms.v5.jsonl"),
                           records.arm_v5_record(run, meta, case.base))
        for hop in observe(case, run, None, None).hops:
            records.append_row(records.run_file(run_dir, run_id, "<run>.hops.jsonl"),
                               records.hop_observation_to_json(hop))
        records.append_row(records.run_file(run_dir, run_id, "<run>.triples.jsonl"),
                           _triple_row(case))
        records.append_row(judge, records.judge_row_to_json(records.JudgeRow(
            case_id=case.base.id, repeat=0, input_sha256="a" * 64,
            verdict=JudgeVerdict(label="верно", reason="«Иванова»", judged_by="model",
                                 cost_usd=0.01))))
        spend += 0.12
    # ONE verdict the residual gate decided before the model was asked. It is
    # written here because the report must be seen counting it APART from the
    # model's (T11) — a fixture with only model verdicts cannot tell the two
    # counts apart.
    records.append_row(judge, records.judge_row_to_json(records.JudgeRow(
        case_id=FIXTURE_BEHAVIOURS[0][0], repeat=0, input_sha256="b" * 64,
        verdict=JudgeVerdict(label="неверно", reason="подмена в ответе",
                             judged_by="residual_gate", cost_usd=0.0))))
    records.run_file(run_dir, run_id, "<run>.spend.tsv").write_text(
        f"agent/{FIXTURE_BEHAVIOURS[0][0]}/0\t{spend:.6f}\ncumulative_usd\t{spend:.6f}\n",
        encoding="utf-8")
    records.run_file(run_dir, run_id, "<run>.meta.json").write_text(json.dumps(
        {"run_id": run_id, "benchmark": "agentpii5", "model": contracts.AGENT_MODEL,
         "judge_model": contracts.JUDGE_MODEL, "tier": "nano", "repeats": 1,
         "digest": "digest-v5", "ceiling_usd": CEILING_USD, "spent_usd": spend,
         "prompt_sha256": PROMPT_SHA}, ensure_ascii=False), encoding="utf-8")
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
        own = v4_half(v5_dir, f"v5 run {run_id_of(v5_dir)}").block
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


def _level_line(block: Sequence[str], label: str) -> str:
    found = [line for line in block if line.startswith("   " + label)]
    if len(found) != 1:
        raise AssertionError(f"v4 printed {len(found)} lines for level {label!r}")
    return found[0]


def _with_verdict(line: str, old: str, new: str) -> str:
    """The same level line with another TOST verdict, in v4's own column.

    `bench/agentpii4/report.py::render` writes `f"{verdict:15} ["`, so the
    verdict is the 15-wide field before the TOST interval; swapping it in place
    keeps every other column byte for byte and the parser is then read on a
    line v4 could really have printed."""
    stamp = old.ljust(15) + " ["
    if stamp not in line:
        raise AssertionError(f"{old!r} is not the verdict of {line!r}")
    return line.replace(stamp, new.ljust(15) + " [", 1)


def test_level_table_reads_every_verdict() -> list[str]:
    """#6 / F2.1 / C-066. v4 prints three TOST verdicts and two of them carry a
    space; the parser read the first token, so «НЕ эквивалентно» and «нет
    данных» were dropped and the side-by-side level table could only ever show
    levels that AGREED — the one table whose job is to show where the gateway
    moved the agent.

    The fixture run really does print «НЕ эквивалентно» (one case: the 1/n
    resolution floor makes the interval two points wide), so the table has six
    rows with the fix and none without it."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        block = list(v4_half(v5_dir, "x").block)
        problems: list[str] = []
        rows = level_rows(block)
        if len(rows) != len(contracts.V4_LEVELS):
            return [f"only {len(rows)} of {len(contracts.V4_LEVELS)} levels parsed: "
                    f"{[row.label for row in rows]}"]
        printed = {row.label: row.tost_verdict for row in rows}
        at_line = {_level_line(block, label): label for _level, label in contracts.V4_LEVELS}

        def _swap(verdict: str) -> list[str]:
            return [_with_verdict(line, printed[at_line[line]], verdict) if line in at_line else line
                    for line in block]

        # Each of the three verdicts v4 can print, on v4's own line.
        for verdict in ("НЕ эквивалентно", "эквивалентно", "нет данных"):
            got = {row.tost_verdict for row in level_rows(_swap(verdict))}
            if got != {verdict}:
                problems.append(f"a block printing {verdict!r} parsed as {got}")
        # A verdict v4 never prints is a REFUSAL, not a dropped row: silence is
        # what let the two real ones disappear.
        try:
            level_rows(_swap("почти эквивалентно"))
            problems.append("an unreadable level line was silently dropped")
        except ReportError:
            pass
        # And the table is PRINTED: the defect was visible as an empty table.
        lines = report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        table = lines[lines.index("--- уровни v4: этот прогон рядом с базовым ---"):]
        for _level, label in contracts.V4_LEVELS:
            if not any(one.startswith("   " + label) for one in table[:8]):
                problems.append(f"the side-by-side level table has no row for {label!r}")
        return problems


def test_missing_hops_file_is_refused() -> list[str]:
    """#5 / F2.2. A run directory without `<run>.hops.jsonl` used to yield
    observations with no hops at all: every hop line went «н/п» and `residual`
    — the critical-defect line — printed a clean 1/1 over them. Reading the
    file «if it exists» is what made a missing measurement look like a clean
    one."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        records.run_file(v5_dir, RUN_ID, "<run>.hops.jsonl").unlink()
        try:
            report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        except ReportError as error:
            return [] if "hops.jsonl" in str(error) else [f"unclear refusal: {error}"]
        return ["a run with no hops file was reported on as a clean run"]


def test_hopless_observation_is_excluded_and_counted() -> list[str]:
    """#5, the other half: the file is THERE and a (case, repeat) has no rows
    in it — a run that died between the arm write and the hop write. That
    observation is excluded, the count is printed and the report is НЕПОЛНЫЙ;
    counting it as clean is how ten hopless observations printed `residual`
    1/1."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        _drop_hops(v5_dir, FIXTURE_BEHAVIOURS[1][0])
        problems: list[str] = []
        half = v5_observations(v5_dir, v4_half(v5_dir, "x").scored)
        if [one.case.base.id for one in half.observations] != [FIXTURE_BEHAVIOURS[0][0]]:
            problems.append(f"the hopless observation was kept: "
                            f"{[one.case.base.id for one in half.observations]}")
        if half.hopless != (f"{FIXTURE_BEHAVIOURS[1][0]}|0",):
            problems.append(f"the hole is not named: {half.hopless}")
        # An EMPTY registry on purpose: the mark asserted here is the one the
        # HOLE sets, and a metric that another module has broken today would
        # otherwise set it too and this test would pass on the wrong reason.
        lines = report_lines(v5_dir, v4_dir, {})
        if contracts.INCOMPLETE_REPORT_MARK not in lines[0]:
            problems.append(f"a run with a hole in it was not marked: {lines[0]!r}")
        if not any("НАБЛЮДЕНИЯ ИСКЛЮЧЕНЫ: 1" in one for one in lines):
            problems.append("the count of excluded observations is not printed")
        return problems


def _drop_hops(run_dir: Path, case_id: str) -> None:
    rows = records.read_rows(records.run_file(run_dir, RUN_ID, "<run>.hops.jsonl"))
    kept = [row for row in rows if row.get("case_id") != case_id]
    records.run_file(run_dir, RUN_ID, "<run>.hops.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in kept), encoding="utf-8")


def test_stopped_arm_is_not_a_hole() -> list[str]:
    """The other cause of an empty `hops` tuple: the arm ended in an
    `EXCLUDED_TERMINATION`, so `observe` was never called on it. v4's own block
    already counts it under «исключено»; marking the report НЕПОЛНЫЙ for it
    would put the word on every real run and teach the reader to scroll past
    the one thing it is for."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        stopped_id = FIXTURE_BEHAVIOURS[1][0]
        path = records.run_file(v5_dir, RUN_ID, "<run>.arms.v5.jsonl")
        rows = records.read_rows(path)
        for row in rows:
            if row.get("case_id") == stopped_id:
                row["termination"] = "timeout"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                        encoding="utf-8")
        _drop_hops(v5_dir, stopped_id)
        problems: list[str] = []
        half = v5_observations(v5_dir, v4_half(v5_dir, "x").scored)
        if half.hopless:
            problems.append(f"an arm that never finished was called a hole: {half.hopless}")
        if half.stopped != (f"{stopped_id}|0 (timeout)",):
            problems.append(f"the stopped arm is not counted: {half.stopped}")
        if [one.case.base.id for one in half.observations] != [FIXTURE_BEHAVIOURS[0][0]]:
            problems.append("a run with nothing observed was scored anyway")
        # The empty registry, for the reason the hole test gives: this asserts
        # the mark is NOT set, and a refused metric elsewhere would set it.
        lines = report_lines(v5_dir, v4_dir, {})
        if contracts.INCOMPLETE_REPORT_MARK in lines[0]:
            problems.append("a run whose only hole is an excluded arm was marked НЕПОЛНЫЙ")
        if not any("плечо не доиграло: 1" in one for one in lines):
            problems.append("the count of unfinished arms is not printed")
        return problems


def test_forged_calibration_stamp_is_recomputed() -> list[str]:
    """#7 / F2.3. The stamp's `calibrated` flag is written by whoever wrote the
    row. With κ=0.21, n=7, another judge model and another prompt hash the
    report printed «откалиброван» and no incompleteness mark at all."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        judge_path = records.run_file(v5_dir, RUN_ID, "<run>.judge.jsonl")
        rows = records.read_rows(judge_path)
        rows[0] = records.calibration_stamp_to_json(CalibrationStamp(
            judge_model=contracts.AGENT_MODEL, prompt_sha256="0" * 64, n=7, raw_agreement=0.40,
            kappa=0.21, per_type_kappa={"NAME": 0.10}, repeat_disagreement=0.9, calibrated=True))
        judge_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                              encoding="utf-8")
        problems: list[str] = []
        side = side_by_side(v5_dir, v4_dir, METRIC_FUNCTIONS)
        if side.judge.calibrated:
            problems.append("a stamp that lies about itself was believed")
        if not side.incomplete:
            problems.append("a report with an uncalibrated judge was not marked НЕПОЛНЫЙ")
        lines = report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        if "НЕ ОТКАЛИБРОВАН" not in lines[1]:
            problems.append(f"the header still says the judge is calibrated: {lines[1]!r}")
        reasons = "\n".join(one for one in lines if "калибровка не принята" in one)
        for wanted in ("судья", "промпт", "размеченных", "сырое согласие", "κ 0.21",
                       "κ по типам", "расхождение повторов"):
            if wanted not in reasons:
                problems.append(f"the refusal does not say {wanted!r}: {reasons!r}")
        # The other side: the honest stamp of the fixture must clear every bar,
        # or «is it uncalibrated» would pass on a report that can never be
        # calibrated.
        if calibration_problems(STAMP, PROMPT_SHA):
            problems.append(f"the honest stamp was refused: {calibration_problems(STAMP, PROMPT_SHA)}")
        # …and the prompt hash is the RUN's, not the stamp's own claim.
        if not calibration_problems(STAMP, "e" * 64):
            problems.append("a calibration of another prompt was accepted")
        return problems


def test_cost_section_is_printed() -> list[str]:
    """G-cost / F2.4. A `--report` replay printed no price at all although
    `<run>.triples.jsonl` and `<run>.spend.tsv` hold every number v4's
    `_cost_lines` needs. The judge's spend gets its own line, and a missing
    file is a printed refusal — «потрачено $0.00» reads as a free run."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        problems: list[str] = []
        lines = report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        text = "\n".join(lines)
        triples = records.read_rows(records.run_file(v5_dir, RUN_ID, "<run>.triples.jsonl"))
        spent = sum(float(one["cost_usd"]) for one in triples)  # type: ignore[arg-type]
        # Through the reader the report itself uses (F2.12): a test that read
        # the nested field would keep passing the day the writer dropped the
        # top-level one, which is the whole defect.
        judge = sum(records.triple_totals_from_json(one).judge_cost_usd for one in triples)
        if "0. ЦЕНА" not in text:
            problems.append("the report prints no price at all")
        elif text.index("0. ЦЕНА") > text.index(V4_BLOCK_START):
            problems.append("the price is printed after v4's block, not before it")
        if f"потрачено ${spent:.2f} из ${CEILING_USD:.2f}" not in text:
            problems.append(f"the spent/ceiling line does not carry the files' numbers "
                            f"(${spent:.2f} / ${CEILING_USD:.2f})")
        if f"судья: ${judge:.2f}" not in text:
            problems.append("the judge's spend is not on its own line")
        if f"spend.tsv: ${spent:.2f}" not in text:
            problems.append("the ledger's own total is not printed beside it")
        # The negative: no triples file → a refusal, never a zero.
        records.run_file(v5_dir, RUN_ID, "<run>.triples.jsonl").unlink()
        refused = "\n".join(cost_lines(v5_dir))
        if "н/д" not in refused or "triples.jsonl" not in refused:
            problems.append(f"a missing triples file did not refuse: {refused!r}")
        if "потрачено $0.00" in refused:
            problems.append("a missing triples file printed a free run")
        return problems


def test_behaviour_blocks_are_printed() -> list[str]:
    """C-043 / C-046 / C-047 / F2.5. v4's levels and taxonomy were scored
    corpus-wide only, so a family's own claim — `same_tool_other_target`'s
    `other_person` count — appeared in no table. One v4 block per behaviour,
    rendered by v4's own `render` over the subset, and `answer_real` by
    behaviour printed among the slices."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        lines = report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS)
        text = "\n".join(lines)
        problems: list[str] = []
        for _case_id, behaviour in FIXTURE_BEHAVIOURS:
            marker = f"--- v4 по поведению: {behaviour} ---"
            if marker not in text:
                problems.append(f"no v4 block for behaviour {behaviour!r}")
                continue
            # It is v4's WHOLE render over the subset, not a level line lifted
            # out of it: the taxonomy table is where `same_tool_other_target`'s
            # `other_person` count lives, and that count is the family's own
            # claim (C-043).
            after = text[text.index(marker):]
            if "4. ТАКСОНОМИЯ ПО ПОЛЯМ" not in after[:after.index("\n---")
                                                     if "\n---" in after else len(after)]:
                problems.append(f"{behaviour}: the block carries no taxonomy table")
        # A behaviour the corpus does not carry must NOT get an empty block —
        # otherwise «one block per behaviour» would pass on eleven empty ones.
        if "--- v4 по поведению: rag ---" in text:
            problems.append("a behaviour with no case in the corpus got a block")
        if "   answer_real/behaviour:" not in text:
            problems.append("answer_real is not printed by behaviour")
        start, end = lines.index(V4_BLOCK_START), lines.index(V4_BLOCK_END)
        at = [index for index, one in enumerate(lines) if one.startswith("--- v4 по поведению:")]
        if at and not all(start < index < end for index in at):
            problems.append("the per-behaviour blocks are outside v4's fence, where their "
                            "«эквивалентно» would read as our claim")
        return problems


def test_every_axis_prints() -> list[str]:
    """C-080 / F2.6. Every axis of `contracts.AXES`, for every line the gate
    let through, in the PRINTED report. The old check called `by_axis` and
    `render_line` itself and never looked at the report, so the slices could
    exist only in memory — and eight of the nine axes did."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        side = side_by_side(v5_dir, v4_dir, METRIC_FUNCTIONS)
        text = "\n".join(report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS))
        problems: list[str] = []
        for name in sorted(side.v5_lines):
            for axis in contracts.AXES:
                if f"   {name}/{axis}: " not in text:
                    problems.append(f"{name}/{axis}: not printed")
        if problems:
            return problems[:6]
        # The negative: an axis nobody buckets by must not be found by the same
        # search, or «is every axis there» would pass on any text.
        if "   leak/несуществующая_ось: " in text:
            problems.append("the search accepts an axis the report never printed")
        return problems


def test_pregate_verdicts_are_counted_apart() -> list[str]:
    """T11 / F2.7. `judged_by == "residual_gate"` is a «неверно» the
    deterministic gate produced before the model was asked. Counted in the
    histogram it credits the judge with verdicts it never gave; counted inside
    the κ the report certifies it measures the gate's agreement with itself."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        parts = read_parts(v5_dir, v4_dir)
        problems: list[str] = []
        if parts.judge.pregate != 1:
            problems.append(f"the pre-gate verdict was not counted apart: {parts.judge.pregate}")
        if parts.judge.labels != {"верно": len(FIXTURE_BEHAVIOURS)}:
            problems.append(f"the model's histogram carries the gate's verdict: {parts.judge.labels}")
        text = "\n".join(report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS))
        if "отказано до судьи (подмена стояла в ответе): 1" not in text:
            problems.append("the pre-gate count has no row of its own")
        if "отказано до судьи: 1" not in text:
            problems.append("the pre-gate count is not printed beside κ")
        if "неверно 1" in text:
            problems.append("the gate's «неверно» is still inside the judge's histogram")
        return problems


def test_differs_histogram() -> list[str]:
    """C-181. Per feature, how many hops named it. The report says «падеж и
    регистр»; a bare «нет» sends nobody anywhere."""
    case = _fixture_case("c-0001", "single")
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
        order = ["0. ЦЕНА", V4_BLOCK_START, V4_BLOCK_END, "2. ЛИНИИ v5", "3. ФОРМА",
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


def _rewrite_triples(run_dir: Path, drop: str) -> None:
    """The triples file again, without one key on the FIRST row. The others
    keep it, so what is being read is «this row is short», not «the file is»."""
    path = records.run_file(run_dir, RUN_ID, "<run>.triples.jsonl")
    rows = records.read_rows(path)
    rows[0].pop(drop)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                    encoding="utf-8")


def test_judge_cost_read_through_records() -> list[str]:
    """F2.12 / R-54. The judge's spend used to be `row.get("judge_cost_usd")`,
    then the nested `judge.cost_usd`, then 0.0 — and «судья: $0.00» is also
    what a run with no judge prints. It is now `records.triple_totals_from_
    json`, which refuses the missing field BY NAME.

    The negative is the exact shape the fallback forgave: a row that has lost
    the top-level key while KEEPING the nested `judge.cost_usd`. Under the old
    reader it printed the nested number and looked right."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        problems: list[str] = []
        rows = records.read_rows(records.run_file(v5_dir, RUN_ID, "<run>.triples.jsonl"))
        want = sum(records.triple_totals_from_json(row).judge_cost_usd for row in rows)
        if f"судья: ${want:.2f}" not in "\n".join(cost_lines(v5_dir)):
            problems.append(f"the judge's spend is not the reader's number (${want:.2f})")
        _rewrite_triples(v5_dir, "judge_cost_usd")
        nested = records.read_rows(records.run_file(v5_dir, RUN_ID, "<run>.triples.jsonl"))[0]
        if not isinstance(nested.get("judge"), dict):
            problems.append("the fixture lost the nested judge row — the negative proves nothing")
        try:
            cost_lines(v5_dir)
            problems.append("a triple with no judge_cost_usd was read from the nested field")
        except ReportError as error:
            if "judge_cost_usd" not in str(error):
                problems.append(f"the refusal does not name the field: {error}")
        return problems


def test_turn_residual_is_demanded_too() -> list[str]:
    """R-54 puts BOTH totals on the triple row and one reader validates both:
    a file that carries the price but not `turn_residual` is not the file the
    report thinks it is, and reading only the half this section needs would
    let the other half rot until the line that prints it goes silent."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, _v4_dir = _built(Path(tmp))
        _rewrite_triples(v5_dir, "turn_residual")
        try:
            cost_lines(v5_dir)
        except ReportError as error:
            return [] if "turn_residual" in str(error) else [f"unclear refusal: {error}"]
        return ["a triple row with no turn_residual was accepted"]


def test_excluded_observations_are_on_the_side() -> list[str]:
    """F2.9. The holes and the arms that stopped are ONE field of the
    `SideBySide`, each row carrying its reason — so a `SideBySide` read back
    from a file still names its own holes instead of trusting whoever
    assembled it. `EXCLUDED_NO_HOPS` is what makes the report НЕПОЛНЫЙ; a
    termination does not."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        hole_id = FIXTURE_BEHAVIOURS[1][0]
        _drop_hops(v5_dir, hole_id)
        problems: list[str] = []
        side = side_by_side(v5_dir, v4_dir, METRIC_FUNCTIONS)
        if side.excluded_observations != (f"{hole_id}|0 ({contracts.EXCLUDED_NO_HOPS})",):
            problems.append(f"the hole is not on the side by side: {side.excluded_observations}")
        if not side.incomplete:
            problems.append("a hole did not make the report НЕПОЛНЫЙ")
        if side.judge_pregate != read_parts(v5_dir, v4_dir).judge.pregate:
            problems.append(f"the pre-gate count is not carried: {side.judge_pregate}")
        # The other reason, on a fresh copy: an arm that STOPPED is listed with
        # its own termination and does NOT mark the report. Without this half,
        # «a hole marks it» would pass on a report that marks everything.
        other, other_v4 = _built(Path(tmp) / "stopped")
        path = records.run_file(other, RUN_ID, "<run>.arms.v5.jsonl")
        rows = records.read_rows(path)
        for row in rows:
            if row.get("case_id") == hole_id:
                row["termination"] = "timeout"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                        encoding="utf-8")
        _drop_hops(other, hole_id)
        stopped = side_by_side(other, other_v4, METRIC_FUNCTIONS)
        if stopped.excluded_observations != (f"{hole_id}|0 (timeout)",):
            problems.append(f"the stopped arm is not on the side by side: "
                            f"{stopped.excluded_observations}")
        if stopped.incomplete:
            problems.append("an arm that stopped marked the report НЕПОЛНЫЙ")
        return problems


def _section_two(lines: list[str]) -> list[str]:
    return lines[lines.index("2. ЛИНИИ v5 — абсолютные доли, интервал Клоппера–Пирсона, "
                             "«сертифицирует ≥» вместо 100%"):
                 lines.index("3. ФОРМА И СРЕЗЫ — каждая напечатанная линия по каждой оси; "
                             "ось одна за раз, никогда две скрещенные")]


def test_out_absent_is_printed_beneath_form_hOUT() -> list[str]:  # noqa: N802 - the metric's name
    """F2.10. `out_absent` counts the declared OUT hops the agent never wrote —
    exactly what `form_hOUT` leaves out of its denominator. Four sections
    apart, `form_hOUT` reads as a form result on every declared hop.

    The negative is another diagnostic: `rewrite_ratio_v5` must NOT sit under
    `form_hOUT` and must be below the diagnostics header, or «the line after
    form_hOUT is a diagnostic» would pass on any ordering at all."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        section = _section_two(report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS))
        problems: list[str] = []
        at = {name: [index for index, one in enumerate(section)
                     if one.strip().startswith(name + " ")]
              for name in ("form_hOUT", "out_absent", "rewrite_ratio_v5")}
        for name, found in at.items():
            if len(found) != 1:
                problems.append(f"{name} is printed {len(found)} times in section 2")
        if problems:
            return problems
        if at["out_absent"][0] != at["form_hOUT"][0] + 1:
            problems.append(f"out_absent is not the line under form_hOUT: {at}")
        header = [index for index, one in enumerate(section) if "диагностика" in one][0]
        if at["out_absent"][0] > header:
            problems.append("out_absent is still printed in the diagnostics block")
        if at["rewrite_ratio_v5"][0] < header:
            problems.append("a diagnostic with no line to qualify was lifted out of the block")
        if BESIDE.get("form_hOUT") != "out_absent":
            problems.append(f"BESIDE no longer pairs the two: {BESIDE}")
        return problems


def test_answer_optional_only_is_printed_beneath_answer_real() -> list[str]:
    """J1.1. `answer_real` stopped judging the answers a case obliges nothing
    in — 720 of the 1357 the corpus declares an answer hop for — and a
    denominator that shrinks without saying so is the defect this pair exists
    to make visible. So the count is printed on the very next line, the way
    `out_absent` is, and not four sections down among the diagnostics where the
    rate above it would read as a rate over every declared answer.

    The negative is the same as `out_absent`'s: a diagnostic with no line to
    qualify (`rewrite_ratio_v5`) must stay BELOW the diagnostics header, or «the
    line after answer_real is a diagnostic» would pass on any ordering."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        section = _section_two(report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS))
        problems: list[str] = []
        at = {name: [index for index, one in enumerate(section)
                     if one.strip().startswith(name + " ")]
              for name in ("answer_real", "answer_optional_only", "rewrite_ratio_v5")}
        for name, found in at.items():
            if len(found) != 1:
                problems.append(f"{name} is printed {len(found)} times in section 2")
        if problems:
            return problems
        if at["answer_optional_only"][0] != at["answer_real"][0] + 1:
            problems.append(f"answer_optional_only is not the line under answer_real: {at}")
        header = [index for index, one in enumerate(section) if "диагностика" in one][0]
        if at["answer_optional_only"][0] > header:
            problems.append("answer_optional_only is printed in the diagnostics block, where the "
                            "reader cannot see which denominator answer_real used")
        if at["rewrite_ratio_v5"][0] < header:
            problems.append("a diagnostic with no line to qualify was lifted out of the block")
        if BESIDE.get("answer_real") != "answer_optional_only":
            problems.append(f"BESIDE no longer pairs the two: {BESIDE}")
        return problems


def test_axis_note_where_a_line_may_not_be_sliced() -> list[str]:
    """F2.10. An observation-level line sliced by a HOP axis counts the same
    answer once per bucket and the buckets add up to more units than the
    corpus holds. `metrics.prints_on_axis` is the one place that says so; the
    report prints `metrics.AXIS_NOTE` instead of the row, because a slice that
    silently disappears reads as a slice that was clean — and the cells are
    not computed at all, since a number that exists gets printed eventually.

    Both sides on the same axis: `residual` carries the note, `leak` carries
    buckets."""
    with tempfile.TemporaryDirectory() as tmp:
        v5_dir, v4_dir = _built(Path(tmp))
        side = side_by_side(v5_dir, v4_dir, METRIC_FUNCTIONS)
        text = "\n".join(report_lines(v5_dir, v4_dir, METRIC_FUNCTIONS))
        problems: list[str] = []
        if prints_on_axis("residual", "pii_type") or not prints_on_axis("leak", "pii_type"):
            return ["metrics no longer holds residual off the hop axes and leak on them"]
        if f"   residual/pii_type: {AXIS_NOTE}" not in text:
            problems.append("an observation-level line was sliced by a hop axis without the note")
        if "pii_type" in side.v5_by_axis["residual"]:
            problems.append("the buckets nobody may print were computed anyway")
        if f"   leak/pii_type: {AXIS_NOTE}" in text:
            problems.append("a hop-sliceable line got the note instead of its buckets")
        if "pii_type" not in side.v5_by_axis["leak"]:
            problems.append("leak lost its hop-axis buckets")
        # A non-hop axis is printed for BOTH: the note is about the axis, not
        # about the metric.
        for name in ("residual", "leak"):
            if f"   {name}/register: {AXIS_NOTE}" in text:
                problems.append(f"{name} got the note on an observation axis")
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
        ("level_table_reads_every_verdict", test_level_table_reads_every_verdict),
        ("missing_hops_file_is_refused", test_missing_hops_file_is_refused),
        ("hopless_observation_is_excluded_and_counted",
         test_hopless_observation_is_excluded_and_counted),
        ("stopped_arm_is_not_a_hole", test_stopped_arm_is_not_a_hole),
        ("forged_calibration_stamp_is_recomputed", test_forged_calibration_stamp_is_recomputed),
        ("cost_section_is_printed", test_cost_section_is_printed),
        ("behaviour_blocks_are_printed", test_behaviour_blocks_are_printed),
        ("every_axis_prints", test_every_axis_prints),
        ("pregate_verdicts_are_counted_apart", test_pregate_verdicts_are_counted_apart),
        ("differs_histogram", test_differs_histogram),
        ("leak_and_coverage_both_present", test_leak_and_coverage_both_present),
        ("no_effect_claims_outside_v4_block", test_no_effect_claims_outside_v4_block),
        ("side_by_side_sections", test_side_by_side_sections),
        ("judge_cost_read_through_records", test_judge_cost_read_through_records),
        ("turn_residual_is_demanded_too", test_turn_residual_is_demanded_too),
        ("excluded_observations_are_on_the_side", test_excluded_observations_are_on_the_side),
        ("out_absent_is_printed_beneath_form_hOUT", test_out_absent_is_printed_beneath_form_hOUT),
        ("answer_optional_only_is_printed_beneath_answer_real",
         test_answer_optional_only_is_printed_beneath_answer_real),
        ("axis_note_where_a_line_may_not_be_sliced", test_axis_note_where_a_line_may_not_be_sliced),
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
