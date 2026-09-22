"""`compare.py` pinned on REAL run directories, written here from hand-built records.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_compare

THE TWO RUNS ARE WRITTEN, NOT MOCKED, for `test_report.py`'s reason: the only
thing a fixture run has to prove is that the writers and the readers agree, and
the honest way to prove it is to write the directory with the writers on every
test run. `build_run` here differs from the report's in ONE way and it is the
point of this file — it takes the arm a case gets, so the same corpus can be
written twice with the gateway behaving differently, which is what «прогон A
против прогона B» means.

EVERY CHECK BELOW GOES RED WITHOUT THE CLAUSE IT NAMES. The four that carry the
statistics are the ones to read first:

  * a comparison of two IDENTICAL runs must print «не отличимо от нуля» with an
    interval AT LEAST ±1/n wide. A percentile bootstrap over identical cases
    returns a zero-width interval and a zero-width interval excludes zero
    however small the difference is — the v4 lesson, in the mirror.
  * a run that differs on every case must print «различие значимо» — an
    instrument that cannot say «different» is not an instrument.
  * a case with nothing in the denominator on one side must be OUT of the
    paired statistic and INSIDE the printed `сравнимо k/K` — v4's defect №1,
    where a triple with nothing to compare passed all five levels.
  * a metric that does not decompose by case must REFUSE its interval by name
    rather than have one drawn around a number nobody computed.
"""
import json
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from bench.agentpii4.records import ArmMeta, arm_record
from bench.agentpii5 import contracts, records
from bench.agentpii5.compare import (
    CONTROL_SUFFIX,
    INDISTINGUISHABLE,
    NOTHING_TO_COMPARE,
    SIGNIFICANT,
    Comparison,
    CompareError,
    LineCells,
    case_rows,
    cells_of,
    compare,
    compare_dirs,
    corpus_digest,
    difference,
    main as compare_main,
    metric_cells,
    read_side,
    render,
)
from bench.agentpii5.contracts import (
    ArmRunV5, CalibrationStamp, CaseV5, JudgeVerdict, Line, MetricRegistry, RunObservation)
from bench.agentpii5.fixtures import (
    FAKE_NAME,
    REAL_NAME,
    REAL_PHONE,
    _call,
    _case,
    _hop,
    _in_message,
    _item,
    _run,
    _with_calls,
    _with_masked,
    _with_mentions,
    _with_replies,
    _with_subs,
)
from bench.agentpii5.metrics import METRIC_FUNCTIONS
from bench.agentpii5.observe import observe
from bench.agentpii5.schema import case_v5_to_json

RUN_A = "compareA0001"
RUN_B = "compareB0001"
PROMPT_SHA = "f" * 64
DIGEST = "digest-v5-shared"
# Six cases and not two: the resolution floor is 1/n, and a fixture of two
# cases would make every interval ±50pp — wide enough to hide the very
# difference the «различие значимо» check has to see.
CASE_IDS: tuple[tuple[str, str], ...] = (
    ("cm-0001", "single"), ("cm-0002", "single"), ("cm-0003", "retry_same_tool"),
    ("cm-0004", "retry_same_tool"), ("cm-0005", "single"), ("cm-0006", "retry_same_tool"))
NAME = _item("p1", "NAME", REAL_NAME, REAL_NAME, "i1", _in_message(1, 0, len(REAL_NAME)))
PHONE = _item("p2", "PHONE", REAL_PHONE, REAL_PHONE, "i1", _in_message(1, 15, 27))
STAMP = CalibrationStamp(judge_model=contracts.JUDGE_MODEL, prompt_sha256=PROMPT_SHA, n=300,
                         raw_agreement=0.88, kappa=0.74, per_type_kappa={"NAME": 0.76},
                         repeat_disagreement=0.04, calibrated=True)


# --- a corpus written twice -----------------------------------------------------------------

def fixture_case(case_id: str, behaviour: str) -> CaseV5:
    """One case with its OWN cluster.

    `fixtures._case` gives every case the same cluster (one person), which is
    right for a metric fixture and wrong here: the bootstrap resamples
    CLUSTERS, and a corpus that is one cluster resamples one thing six times —
    every draw identical, every interval zero-width, and the floor check would
    pass for the wrong reason."""
    in_user = _hop("IN", "user", "p1", 0, 1, "", -1, -1, "")
    out_arg = _hop("OUT", "tool_arg", "p1", 1, 1, "crm_upsert_contact", 0, -1, "contact.last_name")
    answer = _hop("OUT", "answer", "p1", 2, 1, "", -1, -1, "")
    case = _case(case_id, behaviour, ("ты оператор", f"{REAL_NAME}, {REAL_PHONE}"),
                 (NAME, PHONE), (in_user, out_arg, answer))
    return replace(case, base=replace(case.base, cluster=f"NAME:{case_id}"))


# The span the gateway replaced in message 1 — the NAME and only the NAME. The
# PHONE of the same message is declared and left alone ON PURPOSE: a run in
# which everything was masked cannot show what a LEAK looks like, and a leak is
# the one failure the aggregates are structurally unable to see.
NAME_SPAN: dict[int, tuple[tuple[int, int], ...]] = {1: ((0, len(REAL_NAME)),)}


def good_arm(case: CaseV5) -> ArmRunV5:
    """The gateway restored the real surname into the call and into the answer."""
    run = _with_masked(_with_subs(_run(case.base.id), {"p1": FAKE_NAME}), NAME_SPAN)
    run = _with_replies(run, "Готово, Пахомовой.", "Готово, Ивановой.", "Готово, Ивановой.")
    run = _with_calls(run, (_call("crm_upsert_contact", {"contact": {"last_name": "Пахомовой"}},
                                  {"contact": {"last_name": "Ивановой"}}, {}, "", 0),), (1,))
    return _with_mentions(run, (contracts.MentionRecord("p1", 1, -1, FAKE_NAME, 0),))


def broken_arm(case: CaseV5) -> ArmRunV5:
    """The same run with the SUBSTITUTE left standing in the tool argument and
    in the answer — a residual, which is the defect the product exists to
    prevent and the one a comparison of two engine builds has to be able to
    see."""
    run = _with_masked(_with_subs(_run(case.base.id), {"p1": FAKE_NAME}), NAME_SPAN)
    run = _with_replies(run, "Готово, Пахомовой.", "Готово, Пахомовой.", "Готово, Ивановой.")
    run = _with_calls(run, (_call("crm_upsert_contact", {"contact": {"last_name": "Пахомовой"}},
                                  {"contact": {"last_name": "Пахомовой"}},
                                  {"contact.last_name": (FAKE_NAME,)}, "", 0),), (1,))
    return _with_mentions(run, (contracts.MentionRecord("p1", 1, -1, FAKE_NAME, 0),))


def build_run(root: Path, run_id: str, digest: str, cases: Sequence[CaseV5],
              arm_of: Callable[[CaseV5], ArmRunV5], label: str) -> Path:
    """One run directory on disk, exactly the files `contracts.RUN_FILES` names.

    `arm_of` is the seam: the SAME corpus written with a different gateway is
    the only way to test a run-against-run tool without a live model."""
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = ArmMeta("fixture", 1, 0, "sess", "success", False, None, (), "", 0.0)
    (run_dir / "corpus.json").write_text(json.dumps(
        {"corpus": [case.base.to_json() for case in cases], "digest": digest + "-v4"},
        ensure_ascii=False), encoding="utf-8")
    (run_dir / "corpus.v5.json").write_text(json.dumps(
        {"corpus": [case_v5_to_json(case) for case in cases], "digest": digest},
        ensure_ascii=False), encoding="utf-8")
    judge = records.run_file(run_dir, run_id, "<run>.judge.jsonl")
    records.append_row(judge, records.calibration_stamp_to_json(STAMP))
    spend = 0.0
    for case in cases:
        run = arm_of(case)
        for arm in ("C", "I", "C2"):
            records.append_row(records.run_file(run_dir, run_id, "<run>.arms.jsonl"),
                               arm_record(replace(run.base, arm=arm), meta, case.base))
        records.append_row(records.run_file(run_dir, run_id, "<run>.arms.v5.jsonl"),
                           records.arm_v5_record(run, meta, case.base))
        for hop in observe(case, run, None, None).hops:
            records.append_row(records.run_file(run_dir, run_id, "<run>.hops.jsonl"),
                               records.hop_observation_to_json(hop))
        records.append_row(records.run_file(run_dir, run_id, "<run>.triples.jsonl"), {
            "case_id": case.base.id, "repeat": 0, "kind": case.base.kind,
            "behaviour": case.behaviour, "register": case.base.register,
            "cluster": case.base.cluster, "cap_usd": 0.06, "cost_usd": 0.12,
            "status": "complete", "reason": "",
            "arms": {arm: {"termination": "done", "cost_usd": 0.04, "calls": 1, "reason": ""}
                     for arm in ("C", "I", "C2")},
            "judge": {"label": "верно", "judged_by": "model", "cost_usd": 0.01},
            **records.triple_totals_to_json(
                records.TripleTotals(judge_cost_usd=0.01, turn_residual=0))})
        records.append_row(judge, records.judge_row_to_json(records.JudgeRow(
            case_id=case.base.id, repeat=0, input_sha256="a" * 64,
            verdict=JudgeVerdict(label="верно", reason="«Ивановой»", judged_by="model",
                                 cost_usd=0.01))))
        spend += 0.12
    records.run_file(run_dir, run_id, "<run>.spend.tsv").write_text(
        f"cumulative_usd\t{spend:.6f}\n", encoding="utf-8")
    records.run_file(run_dir, run_id, "<run>.meta.json").write_text(json.dumps(
        {"run_id": run_id, "benchmark": "agentpii5", "model": contracts.AGENT_MODEL,
         "judge_model": contracts.JUDGE_MODEL, "tier": "nano", "repeats": 1,
         "digest": digest, "ceiling_usd": 12.0, "spent_usd": spend,
         "prompt_sha256": PROMPT_SHA, "label": label}, ensure_ascii=False), encoding="utf-8")
    return run_dir


def both(root: Path, b_arm: Callable[[CaseV5], ArmRunV5], b_digest: str,
         b_cases: Sequence[CaseV5] | None) -> tuple[Path, Path]:
    """Run A (a right gateway) and run B, built as the caller asks."""
    cases = [fixture_case(case_id, behaviour) for case_id, behaviour in CASE_IDS]
    a = build_run(root, RUN_A, DIGEST, cases, good_arm, "до правки")
    b = build_run(root, RUN_B, b_digest, cases if b_cases is None else b_cases, b_arm,
                  "после правки")
    return a, b


# --- a registry a test controls ---------------------------------------------------------------

def toy_registry(hits_of: Callable[[RunObservation], int],
                 total_of: Callable[[RunObservation], int]) -> MetricRegistry:
    """One metric whose value a test decides, so the statistics can be pinned
    without depending on what a real metric says about a fixture run.

    `compare` takes the registry for the reason `report.assemble` does: a tool
    that could only ever be driven by the real metrics is a tool nobody has
    watched refuse."""
    def metric(observations: Sequence[RunObservation]) -> Line:
        return Line("toy", sum(hits_of(one) for one in observations),
                    sum(total_of(one) for one in observations))
    return {"toy": metric}


def _compare(a_dir: Path, b_dir: Path, functions: MetricRegistry,
             refused: dict[str, str]) -> Comparison:
    return compare(read_side(a_dir), read_side(b_dir), functions, refused,
                   across_corpora=False, reps=200, seed=0)


def _with_argv(argv: list[str], entry: Callable[[], int]) -> int:
    """Run a module's `main()` on a chosen command line.

    The package's entry points read `sys.argv` and take no argument — the house
    shape — so the command line is set here rather than by giving `main` a
    parameter no production caller would ever pass.
    """
    saved = sys.argv
    sys.argv = ["prog", *argv]
    try:
        return entry()
    finally:
        sys.argv = saved


# --- checks ---------------------------------------------------------------------------------

def test_no_pseudex() -> list[str]:
    """The comparison reads files. An engine import here would mean the numbers
    depend on the branch the comparison was run from, not on the runs."""
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_neither_side_is_the_baseline() -> list[str]:
    """Пункт 5. No assumption that either run is v4 or «before».

    Two clauses, and the second is the one with teeth: the header says which
    way the difference is signed, and SWAPPING the two directories negates
    every difference instead of changing which numbers are printed. A tool that
    treated its first argument as the truth would keep the same sign, or print
    a different set of lines, when the arguments are exchanged."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), broken_arm, DIGEST, None)
        forward = compare_dirs(a_dir, b_dir, False, 200, 0)
        backward = compare_dirs(b_dir, a_dir, False, 200, 0)
        if "B − A" not in "\n".join(render(forward, False, 0)):
            problems.append("the header does not say which way the difference is signed")
        mirrored = {diff.name: diff for diff in backward.diffs}
        if {diff.name for diff in forward.diffs} != set(mirrored):
            problems.append("swapping the two runs changed WHICH lines are printed")
        for diff in forward.diffs:
            other = mirrored.get(diff.name)
            if other is None:
                continue
            if diff.delta is None or other.delta is None:
                if (diff.delta is None) != (other.delta is None):
                    problems.append(f"{diff.name}: «н/д» on one side only")
                continue
            if abs(diff.delta + other.delta) > 1e-12:
                problems.append(f"{diff.name}: swapping the runs gave {other.delta}, "
                                f"not the negation of {diff.delta}")
                break
            if abs(diff.effect + other.effect) > 1e-12:
                problems.append(f"{diff.name}: the paired effect is not mirrored "
                                f"({diff.effect} against {other.effect})")
                break
    return problems


def test_every_line_of_both_runs_and_the_difference() -> list[str]:
    """Пункт 5. Every printable metric line of BOTH runs and the difference,
    plus the six v4 levels with their control halves — a comparison that
    printed a subset would be blind exactly where it was not looking."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), broken_arm, DIGEST, None)
        comparison = compare_dirs(a_dir, b_dir, False, 200, 0)
        printed = {diff.name for diff in comparison.diffs}
        for level, _label in contracts.V4_LEVELS:
            if level not in printed or level + CONTROL_SUFFIX not in printed:
                problems.append(f"the v4 level {level!r} is missing from the comparison")
        for name in METRIC_FUNCTIONS:
            if name not in printed and name not in comparison.refused:
                problems.append(f"{name}: neither compared nor refused")
        text = "\n".join(render(comparison, False, 0))
        for diff in comparison.diffs:
            if diff.a.total and f"{diff.a.hits:>4}/{diff.a.total:<6}" not in text:
                problems.append(f"{diff.name}: run A's fraction is not printed")
                break
        if "Δ" not in text:
            problems.append("no difference column is printed")
    return problems


def test_cases_present_in_one_run_only_are_named() -> list[str]:
    """Пункт 5. A case one run has and the other does not is NAMED, and the
    shared basis is the intersection — otherwise a difference of populations
    reads as a difference of engines."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        cases = [fixture_case(case_id, behaviour) for case_id, behaviour in CASE_IDS]
        a_dir = build_run(Path(tmp), RUN_A, DIGEST, cases, good_arm, "A")
        b_dir = build_run(Path(tmp), RUN_B, DIGEST, cases[:-1], good_arm, "B")
        comparison = compare_dirs(a_dir, b_dir, False, 200, 0)
        if comparison.only_a != (CASE_IDS[-1][0],):
            problems.append(f"the case only run A has is not named: {comparison.only_a}")
        if len(comparison.shared) != len(CASE_IDS) - 1:
            problems.append(f"the shared basis is {len(comparison.shared)}, "
                            f"not the {len(CASE_IDS) - 1} cases both runs hold")
        text = "\n".join(render(comparison, False, 0))
        if CASE_IDS[-1][0] not in text:
            problems.append("the header does not print the id of the case only one run has")
    return problems


def test_different_corpora_are_refused() -> list[str]:
    """Пункт 5. Runs on different corpora are REFUSED; `--across-corpora` makes
    the comparison possible and says in the header that it is by shared id."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, "digest-другой", None)
        refused = False
        try:
            compare_dirs(a_dir, b_dir, False, 200, 0)
        except CompareError as error:
            refused = True
            if "--across-corpora" not in str(error):
                problems.append(f"the refusal does not say how to proceed: {error}")
        if not refused:
            problems.append("two runs on different corpora were compared without a word")
        comparison = compare_dirs(a_dir, b_dir, True, 200, 0)
        head = "\n".join(render(comparison, False, 0)[:8])
        if "--across-corpora" not in head or "общая основа" not in head:
            problems.append(f"the across-corpora header does not state the shared basis: {head}")
    return problems


def test_equal_corpora_are_not_refused() -> list[str]:
    """The negative of the check above: a refusal that fired on EVERY pair
    would make `--across-corpora` the only working mode and prove nothing."""
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), broken_arm, DIGEST, None)
        comparison = compare_dirs(a_dir, b_dir, False, 200, 0)
        return [] if comparison.shared else ["two runs of one corpus shared no case"]


def test_identical_runs_are_indistinguishable_with_the_floor() -> list[str]:
    """Пункт 8. Two identical runs: the effect is zero, the verdict is «не
    отличимо от нуля», and the interval is AT LEAST ±1/n wide.

    THE FLOOR IS THE CHECK. A percentile bootstrap over identical cases returns
    a zero-width interval; `[0.0, 0.0]` excludes nothing but it also excludes
    zero by no margin, and a tool that read it literally would call every
    difference significant the moment one case moved. v4 learned this on the
    other side of the same coin — a zero-width interval certifies ANY margin."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, DIGEST, None)
        functions = toy_registry(lambda one: 1, lambda one: 1)
        comparison = _compare(a_dir, b_dir, functions, {})
        toy = next(diff for diff in comparison.diffs if diff.name == "toy")
        if toy.effect != 0.0 or toy.delta != 0.0:
            problems.append(f"identical runs differ: effect {toy.effect}, delta {toy.delta}")
        if toy.verdict != INDISTINGUISHABLE:
            problems.append(f"identical runs got the verdict {toy.verdict!r}")
        floor = 2.0 / toy.comparable
        if toy.high - toy.low < floor - 1e-9:
            problems.append(f"the interval [{toy.low}, {toy.high}] is narrower than the "
                            f"resolution floor 2/n = {floor}: zero width certifies anything")
        text = "\n".join(render(comparison, False, 0))
        if f"при n={toy.comparable}" not in text:
            problems.append("«не отличимо от нуля» is printed without the n it is honest about")
    return problems


def test_a_real_difference_is_significant() -> list[str]:
    """Пункт 8. An instrument that cannot say «different» is not an instrument:
    a line that is 1/1 in A and 0/1 in B on every case must be significant and
    its interval must lie wholly below zero."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, DIGEST, None)
        a_side, b_side = read_side(a_dir), read_side(b_dir)
        ids = {one.case.base.id for one in a_side.observations}
        clusters = {case_id: case.cluster for case_id, case in a_side.cases.items()}
        a_cells = metric_cells("toy", toy_registry(lambda one: 1, lambda one: 1)["toy"],
                               [one for one in a_side.observations if one.case.base.id in ids])
        b_cells = metric_cells("toy", toy_registry(lambda one: 0, lambda one: 1)["toy"],
                               [one for one in b_side.observations if one.case.base.id in ids])
        diff = difference("toy", a_cells, b_cells, clusters, reps=200, seed=0)
        if diff.verdict != SIGNIFICANT:
            problems.append(f"a −100pp difference got the verdict {diff.verdict!r}")
        if diff.high >= 0.0:
            problems.append(f"the interval [{diff.low}, {diff.high}] reaches zero on a line "
                            f"that lost every case")
        if abs(diff.effect + 1.0) > 1e-9:
            problems.append(f"the paired effect is {diff.effect}, not −1.0")
    return problems


def test_a_case_with_nothing_to_compare_is_out_and_counted() -> list[str]:
    """Пункт 8 and v4's defect №1. A case whose denominator is zero in one run
    contributes NOTHING to the paired statistic and is visible in `сравнимо
    k/K` — a pair with nothing to compare must not vote «they agree»."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, DIGEST, None)
        a_side, b_side = read_side(a_dir), read_side(b_dir)
        ids = {one.case.base.id for one in a_side.observations}
        clusters = {case_id: case.cluster for case_id, case in a_side.cases.items()}
        mute = sorted(ids)[0]
        a_cells = metric_cells("toy", toy_registry(lambda one: 1, lambda one: 1)["toy"],
                               [one for one in a_side.observations if one.case.base.id in ids])
        b_cells = metric_cells(
            "toy",
            toy_registry(lambda one: 0 if one.case.base.id == mute else 1,
                         lambda one: 0 if one.case.base.id == mute else 1)["toy"],
            [one for one in b_side.observations if one.case.base.id in ids])
        diff = difference("toy", a_cells, b_cells, clusters, reps=200, seed=0)
        if diff.comparable != len(ids) - 1:
            problems.append(f"сравнимо {diff.comparable}, expected {len(ids) - 1}: the case with "
                            f"an empty denominator was not dropped")
        if diff.cases != len(ids):
            problems.append(f"the shared case count is {diff.cases}, not {len(ids)}")
        if diff.effect != 0.0:
            problems.append(f"the dropped case moved the effect to {diff.effect}")
    return problems


def test_a_line_that_does_not_decompose_refuses_its_interval() -> list[str]:
    """Пункт 8. A metric that counts across case boundaries cannot be summed
    into a paired statistic, and the tool says so BY NAME instead of drawing an
    interval around a number nobody computed."""
    problems: list[str] = []

    def across(observations: Sequence[RunObservation]) -> Line:
        # One hit for the population, whatever it holds: over the whole run it
        # is 1/1, over each of six cases it is 1/1 six times, and the two
        # cannot both be the line.
        return Line("across", 1, 1)

    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, DIGEST, None)
        comparison = _compare(a_dir, b_dir, {"across": across}, {})
        diff = next(one for one in comparison.diffs if one.name == "across")
        if diff.verdict != NOTHING_TO_COMPARE:
            problems.append(f"a non-decomposing line got the verdict {diff.verdict!r}")
        if "не раскладывается" not in diff.why:
            problems.append(f"the refusal does not name the reason: {diff.why!r}")
        if (diff.low, diff.high) != (0.0, 0.0):
            problems.append("an interval was drawn for a line that cannot be decomposed")
        text = "\n".join(render(comparison, False, 0))
        if "не раскладывается" not in text:
            problems.append("the printed line does not carry the refusal")
    return problems


def test_a_refused_metric_is_not_compared() -> list[str]:
    """The report's gate decides what may be printed; the comparison obeys it.
    A metric the gate refuses must appear in the refusals block and in no line
    — two tools printing different sets of numbers about one run is how a
    reader ends up quoting the one that was never allowed to print."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, DIGEST, None)
        comparison = _compare(a_dir, b_dir, toy_registry(lambda one: 1, lambda one: 1),
                              {"toy": "фикстура «zero» напечатала 1/1"})
        if any(diff.name == "toy" for diff in comparison.diffs):
            problems.append("a refused metric was compared anyway")
        text = "\n".join(render(comparison, False, 0))
        if "toy: фикстура" not in text:
            problems.append("the refusal is not printed")
    return problems


def test_no_equivalence_claim() -> list[str]:
    """«Эквивалентно» is a word only TOST earns, and the report reserves it for
    the v4 block. A comparison that printed it would hand a reader a claim
    about a difference being ABSENT from a test that only ever answers whether
    one was FOUND."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        # BOTH shapes, because the word could hide in either verdict: two
        # identical runs («не отличимо от нуля» on every line) and two runs that
        # differ on every case («различие значимо» on several). A scan of the
        # first alone never renders the second verdict at all, and a test that
        # cannot see a string cannot forbid it.
        same_dir, _ = both(Path(tmp) / "same", good_arm, DIGEST, None)
        moved_a, moved_b = both(Path(tmp) / "moved", broken_arm, DIGEST, None)
        for label, pair in (("одинаковые прогоны", (same_dir, same_dir)),
                            ("разные прогоны", (moved_a, moved_b))):
            comparison = compare_dirs(pair[0], pair[1], False, 200, 0)
            text = "\n".join(render(comparison, True, 20))
            bad = [line for line in text.splitlines() if "эквивалент" in line.casefold()]
            if bad:
                problems.append(f"{label}: the comparison claims equivalence: {bad}")
            if label == "разные прогоны" and SIGNIFICANT not in text:
                problems.append("the «разные прогоны» half rendered no significant verdict — "
                                "the scan would pass on any wording")
    return problems


def test_an_empty_denominator_has_no_difference() -> list[str]:
    """`Line.rate` is 0.0 on an empty line, so subtracting the rates of a line
    one run measured and the other did not prints «−100pp» — «B got worse»,
    when the truth is «B measured nothing». A difference nobody can compute is
    «н/д», never a number."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, DIGEST, None)
        a_side, b_side = read_side(a_dir), read_side(b_dir)
        clusters = {case_id: case.cluster for case_id, case in a_side.cases.items()}
        a_cells = metric_cells("toy", toy_registry(lambda one: 1, lambda one: 1)["toy"],
                               list(a_side.observations))
        b_cells = metric_cells("toy", toy_registry(lambda one: 0, lambda one: 0)["toy"],
                               list(b_side.observations))
        diff = difference("toy", a_cells, b_cells, clusters, reps=200, seed=0)
        if diff.delta is not None:
            problems.append(f"a line B never measured produced a difference of {diff.delta}")
        if diff.verdict != NOTHING_TO_COMPARE:
            problems.append(f"an unmeasured line got the verdict {diff.verdict!r}")
    return problems


def test_the_interval_stays_inside_the_range() -> list[str]:
    """A difference of two rates lives in [−100, +100]pp. The 1/n floor widens
    the interval and can push a bound outside that range; the bound is clamped,
    which cannot rescue a verdict (zero is inside the range) and keeps the tool
    from printing a number no reader will trust."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, DIGEST, None)
        a_side, b_side = read_side(a_dir), read_side(b_dir)
        clusters = {case_id: case.cluster for case_id, case in a_side.cases.items()}
        a_cells = metric_cells("toy", toy_registry(lambda one: 1, lambda one: 1)["toy"],
                               list(a_side.observations))
        b_cells = metric_cells("toy", toy_registry(lambda one: 0, lambda one: 1)["toy"],
                               list(b_side.observations))
        diff = difference("toy", a_cells, b_cells, clusters, reps=200, seed=0)
        if diff.low < -1.0 or diff.high > 1.0:
            problems.append(f"the interval [{diff.low}, {diff.high}] leaves the range a "
                            f"difference of rates can live in")
        if diff.verdict != SIGNIFICANT:
            problems.append(f"the clamp changed the verdict to {diff.verdict!r}")
    return problems


def test_cases_table_is_sorted_by_worsening() -> list[str]:
    """Пункт 6. `--cases` prints the case × line table, worst first, with the
    family and the register of each case."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), broken_arm, DIGEST, None)
        comparison = compare_dirs(a_dir, b_dir, False, 200, 0)
        rows = comparison.rows
        if not rows:
            problems.append("a run with a residual on every case moved no cell at all")
        changes = [row.change for row in rows]
        if changes != sorted(changes):
            problems.append("the table is not sorted by how much the cell got worse")
        if rows and rows[0].change >= 0.0:
            problems.append(f"the worst row is an improvement ({rows[0].change})")
        text = "\n".join(render(comparison, True, 200))
        for row in rows[:3]:
            if row.case_id not in text or row.line not in text:
                problems.append(f"{row.case_id}/{row.line} is missing from the printed table")
                break
            if f"{row.family}/{row.register}" not in text:
                problems.append("the table does not carry the family and the register")
                break
        if "СЛУЧАЙ × СТРОКА" not in text:
            problems.append("the table has no heading")
    return problems


def test_cases_table_only_with_the_flag() -> list[str]:
    """The negative of the check above: a table that printed anyway would make
    `--cases` decoration, and a flag that changes nothing teaches a reader that
    flags change nothing."""
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), broken_arm, DIGEST, None)
        comparison = compare_dirs(a_dir, b_dir, False, 200, 0)
        text = "\n".join(render(comparison, False, 40))
        return ["the case table printed without --cases"] if "СЛУЧАЙ × СТРОКА" in text else []


def test_unchanged_cells_stay_out_of_the_table() -> list[str]:
    """A diff table that listed every cell would be the run itself, printed
    twice: only cells whose value MOVED belong in it."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, DIGEST, None)
        comparison = compare_dirs(a_dir, b_dir, False, 200, 0)
        if comparison.rows:
            problems.append(f"identical runs produced {len(comparison.rows)} changed cells: "
                            f"{[ (row.case_id, row.line) for row in comparison.rows[:4] ]}")
    return problems


def test_population_change_is_not_a_value_change() -> list[str]:
    """A cell that lost its denominator is a change of POPULATION, and the
    table says so («n/a») instead of ranking it among the regressions: a case
    the run never reached must not masquerade as a case the gateway broke."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, DIGEST, None)
        a_side, b_side = read_side(a_dir), read_side(b_dir)
        ids = {one.case.base.id for one in a_side.observations}
        mute = sorted(ids)[0]
        a_cells = {"toy": metric_cells(
            "toy", toy_registry(lambda one: 1, lambda one: 1)["toy"],
            list(a_side.observations))}
        b_cells = {"toy": metric_cells(
            "toy",
            toy_registry(lambda one: 0 if one.case.base.id == mute else 1,
                         lambda one: 0 if one.case.base.id == mute else 1)["toy"],
            list(b_side.observations))}
        rows = case_rows(a_cells, b_cells, a_side.cases)
        muted = [row for row in rows if row.case_id == mute]
        if len(muted) != 1:
            problems.append(f"the case that lost its denominator produced {len(muted)} rows")
        elif muted[0].change != 0.0:
            problems.append(f"an empty denominator was ranked as a change of {muted[0].change}")
        elif rows[-1].case_id != mute:
            problems.append("the population change is not sorted last")
    return problems


def test_a_run_without_meta_still_compares() -> list[str]:
    """`<run>.meta.json` is context, not a denominator. A run that wrote none is
    compared and its header says «—» — never a plausible tier or model invented
    to fill the column, and never a refusal that would make an older run
    uncomparable for carrying less."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), good_arm, DIGEST, None)
        records.run_file(b_dir, RUN_B, "<run>.meta.json").unlink()
        comparison = compare_dirs(a_dir, b_dir, False, 200, 0)
        head = "\n".join(render(comparison, False, 0)[:6])
        if f"B {b_dir}" not in head:
            problems.append("a run without meta.json is missing from the header")
        if "ярус — · модель —" not in head:
            problems.append(f"the header invented a value for a field the run never wrote:\n{head}")
        if not comparison.shared:
            problems.append("a run without meta.json was not compared at all")
    return problems


def test_corpus_digest_tells_missing_from_unnamed() -> list[str]:
    """§2.1. `report._digest` returns "" for both «no corpus» and «no digest
    key»; a comparison has to tell them apart, because one means «this is not a
    run» and the other means «these runs cannot be certified to share a
    corpus»."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, _b_dir = both(Path(tmp), good_arm, DIGEST, None)
        if corpus_digest(a_dir) != DIGEST:
            problems.append("the digest of a written run is not read back")
        corpus = a_dir / "corpus.v5.json"
        raw = json.loads(corpus.read_text(encoding="utf-8"))
        del raw["digest"]
        corpus.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        if corpus_digest(a_dir) != "":
            problems.append("a corpus that names no digest was given one")
        corpus.unlink()
        missing = False
        try:
            corpus_digest(a_dir)
        except CompareError as error:
            missing = True
            if "corpus.v5.json" not in str(error):
                problems.append(f"the refusal does not name the file: {error}")
        if not missing:
            problems.append("a directory with no corpus was read as a run")
    return problems


def test_a_directory_that_is_not_a_run_is_refused_by_the_command() -> list[str]:
    """The CLI answers a wrong path with a refusal and exit 2, not a traceback.

    `_load_run` falls back to v4's committed `corpus.json` when a directory
    carries none, so a path that is not a run at all otherwise gets three
    readers deep before anything is said — and what it says then is a
    traceback, which tells the reader their tool is broken when their path is."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "не-прогон"
        empty.mkdir()
        code = _with_argv([str(empty), str(empty)], compare_main)
        if code != 2:
            problems.append(f"a directory that is not a run exited {code}, not 2")
        # AND the half-copied run, which is the likelier accident: a directory
        # with the corpus and no `<run>.hops.jsonl`. That one is refused by
        # `report.observations_of` — the reader that owns the file — so the
        # command has to answer for a refusal that is not its own error type.
        a_dir, b_dir = both(Path(tmp) / "половина", good_arm, DIGEST, None)
        records.run_file(b_dir, RUN_B, "<run>.hops.jsonl").unlink()
        code = _with_argv([str(a_dir), str(b_dir)], compare_main)
        if code != 2:
            problems.append(f"a run missing its hops file exited {code}, not 2")
    return problems


def test_real_metrics_move_between_the_two_runs() -> list[str]:
    """The end-to-end shape: the two fixture runs differ by a residual, and the
    real registry must see it. A comparison that moved NOTHING between a right
    gateway and one that leaves the fake in the tool call would be a
    comparison of nothing."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        a_dir, b_dir = both(Path(tmp), broken_arm, DIGEST, None)
        comparison = compare_dirs(a_dir, b_dir, False, 200, 0)
        moved = [diff.name for diff in comparison.diffs if diff.delta != 0.0]
        if "residual" not in moved:
            problems.append(f"`residual` did not move on a run full of residuals: {moved}")
        for diff in comparison.diffs:
            if diff.name == "residual" and diff.delta >= 0.0:
                problems.append(f"`residual` improved when the fake reached the tool: {diff.delta}")
    return problems


def test_cells_of_covers_the_shared_basis_only() -> list[str]:
    """The lines are computed over the INTERSECTION, not over each run's own
    population: otherwise the Δ column mixes «the engine changed» with «the run
    covered other cases»."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        cases = [fixture_case(case_id, behaviour) for case_id, behaviour in CASE_IDS]
        a_dir = build_run(Path(tmp), RUN_A, DIGEST, cases, good_arm, "A")
        side = read_side(a_dir)
        shared = {case_id for case_id, _behaviour in CASE_IDS[:3]}
        cells = cells_of(side, shared, toy_registry(lambda one: 1, lambda one: 1))
        toy: LineCells = cells["toy"]
        if toy.line.total != len(shared):
            problems.append(f"the line counted {toy.line.total} observations, not the "
                            f"{len(shared)} of the shared basis")
        if set(toy.per_case) != shared:
            problems.append(f"the per-case decomposition covers {sorted(toy.per_case)}")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("neither_side_is_the_baseline", test_neither_side_is_the_baseline),
        ("every_line_of_both_runs_and_the_difference",
         test_every_line_of_both_runs_and_the_difference),
        ("cases_present_in_one_run_only_are_named", test_cases_present_in_one_run_only_are_named),
        ("different_corpora_are_refused", test_different_corpora_are_refused),
        ("equal_corpora_are_not_refused", test_equal_corpora_are_not_refused),
        ("identical_runs_are_indistinguishable_with_the_floor",
         test_identical_runs_are_indistinguishable_with_the_floor),
        ("a_real_difference_is_significant", test_a_real_difference_is_significant),
        ("a_case_with_nothing_to_compare_is_out_and_counted",
         test_a_case_with_nothing_to_compare_is_out_and_counted),
        ("a_line_that_does_not_decompose_refuses_its_interval",
         test_a_line_that_does_not_decompose_refuses_its_interval),
        ("a_refused_metric_is_not_compared", test_a_refused_metric_is_not_compared),
        ("no_equivalence_claim", test_no_equivalence_claim),
        ("an_empty_denominator_has_no_difference", test_an_empty_denominator_has_no_difference),
        ("the_interval_stays_inside_the_range", test_the_interval_stays_inside_the_range),
        ("cases_table_is_sorted_by_worsening", test_cases_table_is_sorted_by_worsening),
        ("cases_table_only_with_the_flag", test_cases_table_only_with_the_flag),
        ("unchanged_cells_stay_out_of_the_table", test_unchanged_cells_stay_out_of_the_table),
        ("population_change_is_not_a_value_change", test_population_change_is_not_a_value_change),
        ("a_run_without_meta_still_compares", test_a_run_without_meta_still_compares),
        ("corpus_digest_tells_missing_from_unnamed", test_corpus_digest_tells_missing_from_unnamed),
        ("a_directory_that_is_not_a_run_is_refused_by_the_command",
         test_a_directory_that_is_not_a_run_is_refused_by_the_command),
        ("real_metrics_move_between_the_two_runs", test_real_metrics_move_between_the_two_runs),
        ("cells_of_covers_the_shared_basis_only", test_cells_of_covers_the_shared_basis_only),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("compare: PASS" if not failures else "compare: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
