"""The gate that refuses to print, and the report it lets through.

TWO JOBS, AND THE FIRST ONE IS THE PRODUCT.

  1. `gate` / `gate_all` — every metric runs the fixtures `fixtures.py`
     declares for it, one per kind in `contracts.FIXTURE_KINDS`, and must print
     exactly the fraction each one declares, with the `zero` fixture at 0.0 and
     the `one` fixture at 1.0. A metric that fails any of that is NOT PRINTED;
     its name and the reason go to `v5_refused`, and a report holding a refused
     NON-diagnostic metric carries `contracts.INCOMPLETE_REPORT_MARK` in its
     header. Not printing is the only sanction that survives a deadline — a
     warning gets read once and then scrolled past, a missing number gets asked
     about.
  2. `render_side_by_side` — the v4 baseline beside the v5 additions, for the
     GO run. The v4 half is produced by `bench.agentpii4.report.render` and
     copied BYTE FOR BYTE; a baseline re-typed here would drift from the
     baseline v4's own tools print, and a baseline that moves with the
     treatment measures nothing (`test_report.test_v4_block_byte_equal`).

«ЭКВИВАЛЕНТНО» IS A WORD ONLY THE v4 BLOCK MAY SAY. «No effect» is a claim
about a DIFFERENCE and only TOST at δ=3pp earns it; the v5 lines are absolute
rates and print an interval and what a flawless line certifies, never a
verdict of equivalence. Pinned by `test_report.test_no_effect_claims_outside_
v4_block`, because the tempting sentence — «форма не пострадала» — is exactly
the sentence a reader would take as a TOST result. The per-behaviour v4 blocks
and the re-rendered level table therefore live INSIDE the fence: they are v4's
own sentences about subsets of the same run, not ours.

A MISSING INPUT IS A PRINTED REFUSAL, NEVER A SILENT ZERO. Three ways this
report used to certify what it had not measured, all three found by the phase-4
review and each pinned by a negative test here:

  * `<run>.hops.jsonl` absent or short — every hop metric went «н/п» and
    `residual` printed a clean 1/1 over the observations that had no hops at
    all. The file is now REQUIRED, and an arm record whose case declares hops
    but whose hop rows never reached the file is EXCLUDED with a count in the
    header (F2.2 / finding #5).
  * the calibration stamp's `calibrated` flag was believed. It is now
    RECOMPUTED from the stamp's own numbers against `contracts.CALIBRATION`,
    from `judge_model` against `contracts.JUDGE_MODEL`, and from
    `prompt_sha256` against the hash the run itself recorded in
    `<run>.meta.json` (F2.3 / finding #7).
  * v4 prints three TOST verdicts and the level parser could read one of them,
    so the side-by-side level table could only ever show agreement
    (F2.1 / finding #6).

Run:  python3 -m bench.agentpii5.report --selftest
      python3 -m bench.agentpii5.report <v5-run-dir> <v4-run-dir>
"""
import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from bench.agentpii4 import report as v4_report
from bench.agentpii4 import stats
from bench.agentpii4.autopsy import _load_run
from bench.agentpii4.report import Scored
from bench.agentpii4.schema import EXCLUDED_TERMINATIONS, Case
from bench.agentpii5 import contracts, records
from bench.agentpii5.contracts import (
    CalibrationStamp,
    CaseV5,
    Fixture,
    GateVerdict,
    HopObservation,
    LevelRow,
    Line,
    Metric,
    RunObservation,
    SideBySide,
)
from bench.agentpii5.fixtures import FIXTURES
from bench.agentpii5 import metrics as metric_bodies
from bench.agentpii5.metrics import AXIS_NOTE, METRIC_FUNCTIONS, by_axis, prints_on_axis
from bench.agentpii5.schema import case_v5_from_json

# The v4 half is fenced so a reader — and `test_no_effect_claims_outside_v4_
# block` — can tell v4's own sentences from ours without guessing.
V4_BLOCK_START = "=== БЛОК v4 — его собственный отчёт, дословно ==="
V4_BLOCK_END = "=== КОНЕЦ БЛОКА v4 ==="
# The discordance and design effect the by-behaviour MDE line assumes. Both are
# v4's measured values on the 07.09 max run, named here so a reader can see the
# assumption instead of inferring it from a number.
MDE_DISCORDANCE = 0.10
MDE_DEFF = 2.1
# THE THREE VERDICTS `stats.tost_equivalence` CAN RETURN, spelled as v4 prints
# them (`bench/agentpii4/report.py::render`, `f"{verdict:15}"`). Two of them
# carry a SPACE, and the former `(?P<verdict>\S+)` matched neither: the table
# could show a level only when it was «эквивалентно», so the one table whose
# job is to show where the gateway moved the agent was structurally incapable
# of showing it (finding #6). An alternation of the exact three is also what
# makes an unknown fourth verdict a refusal instead of a dropped row.
_TOST_VERDICTS: tuple[str, ...] = ("НЕ эквивалентно", "эквивалентно", "нет данных")
_LEVEL_LINE = re.compile(
    r"^\s+(?P<comparable>\d+)/(?P<triples>\d+)\s+"
    r"(?P<ic>[\d.]+%|n/a)\s+(?P<cc>[\d.]+%|n/a)\s+"
    r"(?P<effect>[+-][\d.]+)pp\s+\[\s*(?P<lo>[+-][\d.]+),\s*(?P<hi>[+-][\d.]+)\]\s+"
    r"(?P<verdict>" + "|".join(_TOST_VERDICTS) + r")\s+\[\s*(?P<tl>[+-][\d.]+),\s*(?P<th>[+-][\d.]+)\]\s+"
    r"(?P<p>[\d.]+)\s+\((?P<b>\d+),(?P<c>\d+)\)\s+"
    r"(?P<icc_case>[-\d.]+)\s+(?P<icc_value>[-\d.]+)\s+(?P<deff>[\d.]+)\s*$")
# `out_absent` is DIAGNOSTIC, and it is the one diagnostic that must not be
# read on its own page: it counts the declared OUT hops the agent never wrote,
# which is exactly what `form_hOUT` leaves out of its denominator. Printed with
# the other diagnostics, four sections down, `form_hOUT` reads as a form result
# on every declared hop (F2.10). A mapping and not a hard-coded pair of lines
# so a second such pair is one row here rather than a second special case.
BESIDE: dict[str, str] = {"form_hOUT": "out_absent"}


class ReportError(ValueError):
    """A run directory that cannot be read as a run. Raised with the path and
    the missing file: a report built from half a run would be a report about
    whichever half happened to be there."""


# --- the gate --------------------------------------------------------------------------

def gate(metric: Metric, fixtures: Sequence[Fixture]) -> GateVerdict:
    """One metric against its fixtures — one per kind in
    `contracts.FIXTURE_KINDS`, whatever that tuple holds. NEVER raises on a
    wrong metric: a wrong metric is the finding, and a gate that crashed on it
    would take the whole report down instead of printing the one line that
    matters.

    THERE IS NO SEPARATION COMPARISON ANY MORE (R-55). It read «one minus zero
    ≥ FIXTURE_MIN_SEPARATION» after the exact-fraction check had already
    refused every fixture that printed anything but its declared x/n, and
    `fixtures.py` declares the `zero` fixture at 0/n and the `one` fixture at
    n/n — so the branch could not fire, and a check that cannot go red is
    decoration in the one place of v5 that decides whether numbers are printed
    at all."""
    name = fixtures[0].metric if fixtures else "?"
    kinds = {fixture.kind for fixture in fixtures}
    missing = [kind for kind in contracts.FIXTURE_KINDS if kind not in kinds]
    if missing:
        return GateVerdict(name, False, f"нет фикстур: {', '.join(missing)}")
    for fixture in fixtures:
        try:
            line = metric(fixture.input)
        except Exception as error:  # noqa: BLE001 - the exception IS the verdict
            return GateVerdict(name, False, f"{fixture.name}: метрика упала — {error!r}")
        if (line.hits, line.total) != (fixture.expected_hits, fixture.expected_total):
            return GateVerdict(name, False, f"{fixture.name}: напечатала {line.hits}/{line.total}, "
                                            f"ждали {fixture.expected_hits}/{fixture.expected_total}")
    return GateVerdict(name, True, "")


def gate_all(functions: dict[str, Metric]) -> dict[str, GateVerdict]:
    """Every metric of `functions` against `FIXTURES`.

    The registry is a PARAMETER and not a module lookup, so `--selftest` can
    hand it a deliberately broken one. A gate that could only ever see the real
    functions would be a gate nobody had watched go red — the exact thing
    `e2e/audit_gates.py --selftest` exists to prevent."""
    out: dict[str, GateVerdict] = {}
    for name in sorted(functions):
        fixtures = FIXTURES.get(name)
        if not fixtures:
            out[name] = GateVerdict(name, False, "нет фикстур: метрика не описана в fixtures.py")
            continue
        out[name] = gate(functions[name], fixtures)
    return out


# --- rendering one line ----------------------------------------------------------------

def render_line(line: Line) -> str:
    """«name x/n (p%) [low, high]», and «сертифицирует ≥ f%» instead of 100%.

    A finite sample cannot print 100%: what x = n certifies is the one-sided
    bound `zero_failure_floor(n)` gives, and writing «100%» instead is the
    commonest way a benchmark overstates itself."""
    if line.total == 0:
        return f"{line.name:22} н/п (нет применимых наблюдений)"
    low, high = line.interval
    if line.certified is not None:
        return (f"{line.name:22} {line.hits:5}/{line.total:<5} "
                f"сертифицирует ≥ {100 * line.certified:5.2f}%  [{100 * low:5.1f}, {100 * high:5.1f}]")
    return (f"{line.name:22} {line.hits:5}/{line.total:<5} {100 * line.rate:6.2f}%  "
            f"[{100 * low:5.1f}, {100 * high:5.1f}]")


def differs_histogram(observations: Sequence[RunObservation], pii_type: str) -> dict[str, int]:
    """Per feature of one type, how many observed hops named it as different.

    C-181: the verdict prints the SET. «падеж и регистр» tells an engineer
    where to look; «нет» tells them the line is red and nothing else."""
    features = contracts.FORM_FEATURES.get(pii_type)
    if features is None:
        raise ReportError(f"differs_histogram: {pii_type!r} has no form features; "
                          f"the declared types are {sorted(contracts.FORM_FEATURES)}")
    counts = {feature: 0 for feature in features}
    for one in observations:
        for hop in one.hops:
            if hop.status != "observed" or hop.pii_type != pii_type or hop.verdict is None:
                continue
            for feature in hop.verdict.differs:
                counts[feature] = counts.get(feature, 0) + 1
    return counts


# --- reading a run directory -------------------------------------------------------------

def run_id_of(run_dir: Path) -> str:
    """The run's own id, read off the file names it wrote. Deriving it from the
    directory name would break the moment a run is copied for comparison, which
    is exactly what a side-by-side does."""
    found = sorted(run_dir.glob("*.arms.jsonl"))
    if not found:
        raise ReportError(f"{run_dir}: no <run>.arms.jsonl — not a run directory")
    return found[0].name[: -len(".arms.jsonl")]


@dataclass(frozen=True)
class RunHalf:
    """ONE run directory as v4's own tools read it, read exactly once.

    `block` is v4's report of it verbatim; `scored`, `cases` and `excluded` are
    what v4 produced that block from, kept so the per-behaviour blocks can be
    v4's own render over subsets of the SAME scoring rather than a second one."""

    block: tuple[str, ...]
    scored: tuple[Scored, ...]
    cases: dict[str, Case]
    excluded: tuple[str, ...]


def v4_half(run_dir: Path, header: str) -> RunHalf:
    """v4's own report of a run, and the scored triples behind it.

    Produced by v4's `_load_run` → `score_triples` → `render`, in that order and
    with no v5 argument anywhere: this is the baseline, and the baseline must
    not know it is being compared."""
    cases, triples, excluded = _load_run(run_dir)
    scored = v4_report.score_triples(cases, triples)
    return RunHalf(block=tuple(v4_report.render(cases, scored, excluded, header)),
                   scored=tuple(scored), cases=dict(cases), excluded=tuple(excluded))


def level_rows(block: Sequence[str]) -> tuple[LevelRow, ...]:
    """v4's level lines, parsed back into fields. Read from the printed text on
    purpose — the side-by-side then cannot show a number the v4 block does not.

    A block with NO level line at all is v4's early return on a run with no
    scored triple, and yields no rows. A block that HAS a level line the parser
    cannot read is the finding #6 shape and RAISES: `continue` there is what
    let «НЕ эквивалентно» disappear from the table while the table still
    printed."""
    found: dict[str, list[str]] = {}
    for level, label in contracts.V4_LEVELS:
        found[label] = [line for line in block if line.startswith("   " + label)]
    if not any(found.values()):
        return ()
    wrong = [label for label, lines in found.items() if len(lines) != 1]
    if wrong:
        raise ReportError(f"level_rows: v4's level table is not one line per level for {wrong}; "
                          f"the six levels of `V4_LEVELS` are printed together or not at all")
    out: list[LevelRow] = []
    for level, label in contracts.V4_LEVELS:
        line = found[label][0]
        hit = _LEVEL_LINE.match(line[len("   " + label):])
        if hit is None:
            raise ReportError(f"level_rows: cannot read v4's {label!r} line {line!r}; "
                              f"the verdicts v4 prints are {list(_TOST_VERDICTS)}")
        out.append(LevelRow(
            level=level, label=label, comparable=int(hit["comparable"]), triples=int(hit["triples"]),
            agree_ic=_percent(hit["ic"]), agree_cc=_percent(hit["cc"]),
            effect=float(hit["effect"]) / 100, ci_low=float(hit["lo"]) / 100,
            ci_high=float(hit["hi"]) / 100, tost_verdict=hit["verdict"],
            tost_low=float(hit["tl"]) / 100, tost_high=float(hit["th"]) / 100,
            mcnemar_p=float(hit["p"]), discordant_b=int(hit["b"]), discordant_c=int(hit["c"]),
            icc_case=float(hit["icc_case"]), icc_value=float(hit["icc_value"]),
            deff=float(hit["deff"])))
    return tuple(out)


def _percent(raw: str) -> float:
    return float("nan") if raw.strip() == "n/a" else float(raw.rstrip("%")) / 100


@dataclass(frozen=True)
class V5Half:
    """The v5 observations of a run, and the arm records whose hops are MISSING.

    Three fields and not one because an empty `hops` tuple has three causes a
    report must never confuse:

      * the case declares no hop — nothing to observe, and the observation is
        scored as usual;
      * the arm ended in an `EXCLUDED_TERMINATION` — the run never got far
        enough to cross anything. `observe` is not called on it and v4's own
        block already prints it under «исключено», so it is dropped from the
        v5 population and COUNTED (`stopped`), never marked as a hole;
      * the case declares hops, the arm finished, and its rows are not in
        `<run>.hops.jsonl` — a run that died between the arm write and the hop
        write, or a directory copied without the file. That is a HOLE
        (`hopless`): the observation is dropped, the count is printed, and the
        report is НЕПОЛНЫЙ. Counting it as clean is finding #5 — `residual`
        printed 1/1 over ten observations it had never read a hop of."""

    observations: tuple[RunObservation, ...]
    hopless: tuple[str, ...]
    stopped: tuple[str, ...]


def v5_cases(run_dir: Path) -> dict[str, CaseV5]:
    """The run's own v5 corpus, keyed by the BASE case id.

    `case_v5_to_json` nests the v4 case under "base" so the two corpus files
    carry the same bytes for the v4 half; reading the id off the outer row
    would key every case under None."""
    corpus_path = run_dir / "corpus.v5.json"
    if not corpus_path.exists():
        raise ReportError(f"{run_dir}: no corpus.v5.json — a v5 report needs the v5 corpus")
    loaded = [case_v5_from_json(row)
              for row in json.loads(corpus_path.read_text(encoding="utf-8"))["corpus"]]
    return {case.base.id: case for case in loaded}


def v5_observations(run_dir: Path, scored: Sequence[Scored]) -> V5Half:
    """`observations_of` with the run's own v5 corpus — the entry point a
    caller that holds nothing but the directory uses."""
    return observations_of(run_dir, scored, v5_cases(run_dir))


def observations_of(run_dir: Path, scored: Sequence[Scored],
                    cases: dict[str, CaseV5]) -> V5Half:
    """Rebuild the `RunObservation`s of a v5 run from its files.

    The hops are READ, never recomputed: `observe.py` ran once, during the run,
    on records that are now on disk beside its output, and a report that
    re-derived them could print numbers no run ever produced. That is exactly
    why the file is REQUIRED: reading it «if it exists» turned a run with no
    hops on disk into a run with nothing wrong with it."""
    run_id = run_id_of(run_dir)
    hops: dict[tuple[str, int], list[HopObservation]] = {}
    hops_path = records.run_file(run_dir, run_id, "<run>.hops.jsonl")
    if not hops_path.exists():
        raise ReportError(f"{run_dir}: no {hops_path.name} — every hop metric would print «н/п» and "
                          f"`residual` would certify a run it never read")
    for row in records.read_rows(hops_path):
        one = records.hop_observation_from_json(row)
        hops.setdefault((one.case_id, one.repeat), []).append(one)
    pairs = {(item.triple.case_id, item.triple.repeat): (item.ic, item.cc) for item in scored}
    out: list[RunObservation] = []
    hopless: list[str] = []
    stopped: list[str] = []
    for row in records.merged_v5_records(run_dir):
        run = records.arm_v5_from_record(row)
        case = cases.get(run.base.case_id)
        if case is None:
            raise ReportError(f"{run_dir}: arm record for {run.base.case_id!r} has no v5 case in "
                              f"corpus.v5.json; the run and its corpus are not the same run")
        key = (run.base.case_id, run.base.repeat)
        rows = tuple(hops.get(key, ()))
        if case.hops and not rows:
            name = f"{run.base.case_id}|{run.base.repeat}"
            if run.base.termination in EXCLUDED_TERMINATIONS:
                stopped.append(f"{name} ({run.base.termination})")
            else:
                hopless.append(name)
            continue
        ic, cc = pairs.get(key, (None, None))
        out.append(RunObservation(case=case, repeat=run.base.repeat, hops=rows,
                                  run=run, ic=ic, cc=cc))
    return V5Half(observations=tuple(out), hopless=tuple(sorted(hopless)),
                  stopped=tuple(sorted(stopped)))


@dataclass(frozen=True)
class JudgeHalf:
    """`<run>.judge.jsonl` read back: the stamp, the MODEL's labels, the
    verdicts decided before the model was asked, and why the calibration does
    or does not hold.

    `pregate` is its own number because `judged_by == "residual_gate"` is a
    «неверно» the deterministic gate produced (`judge.residual_pregate_of`);
    counting those in the histogram credits the model with verdicts it never
    gave, and counting them inside the κ that gates publication measures the
    gate's agreement with itself (T11)."""

    stamp: CalibrationStamp | None
    labels: dict[str, int]
    pregate: int
    problems: tuple[str, ...]


def meta_of(run_dir: Path, run_id: str) -> dict[str, object]:
    """`<run>.meta.json`, or {} when the run wrote none. Every caller prints a
    refusal for the field it wanted — the file is not required to READ a run,
    but nothing it carries may be replaced by a default.

    The NAME comes from `contracts.RUN_FILES` through `records.run_file`, not
    from a format string here (F2.9): a second spelling of a run file is one
    rename away from a report that looks for a file no run writes. The BODY is
    read with `json` and not through a `records` reader on purpose — every
    reader there refuses a missing field by name, and this file's absence is a
    legitimate state each caller reports in its own words."""
    path = records.run_file(run_dir, run_id, "<run>.meta.json")
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ReportError(f"{path}: expected an object, found {type(raw).__name__}")
    return {str(key): value for key, value in raw.items()}


def calibration_problems(stamp: CalibrationStamp | None, prompt_sha256: str) -> tuple[str, ...]:
    """Why this stamp does NOT certify the judge, recomputed from its own
    numbers. Empty means calibrated.

    THE FLAG IN THE FILE IS NOT EVIDENCE. `calibrated` is written by whoever
    wrote the row, and a stamp carrying κ=0.21, another model and another
    prompt printed «откалиброван» and a complete report (finding #7). The
    thresholds are `contracts.CALIBRATION`, the model is
    `contracts.JUDGE_MODEL`, and the prompt hash is the one the RUN recorded —
    a calibration of another prompt is a calibration of another instrument."""
    if stamp is None:
        return ("нет калибровочного штампа в <run>.judge.jsonl (строка 0)",)
    bars = contracts.CALIBRATION
    problems: list[str] = []
    if stamp.judge_model != contracts.JUDGE_MODEL:
        problems.append(f"судья {stamp.judge_model!r}, а откалиброван должен быть "
                        f"{contracts.JUDGE_MODEL!r}")
    if not prompt_sha256:
        problems.append("нет <run>.meta.json: хэш промпта судьи не с чем сверить")
    elif stamp.prompt_sha256 != prompt_sha256:
        problems.append(f"штамп про промпт {stamp.prompt_sha256[:12]}, прогон считал "
                        f"{prompt_sha256[:12]}")
    if stamp.n < bars.sample_size:
        problems.append(f"размеченных {stamp.n} < {bars.sample_size}")
    if stamp.raw_agreement < bars.raw_agreement_min:
        problems.append(f"сырое согласие {stamp.raw_agreement:.2f} < {bars.raw_agreement_min}")
    if stamp.kappa < bars.kappa_min:
        problems.append(f"κ {stamp.kappa:.2f} < {bars.kappa_min}")
    if not stamp.per_type_kappa:
        problems.append("нет κ по типам")
    low = sorted(name for name, value in stamp.per_type_kappa.items() if value < bars.kappa_min)
    if low:
        problems.append("κ по типам ниже порога: " + ", ".join(
            f"{name} {stamp.per_type_kappa[name]:.2f}" for name in low))
    if stamp.repeat_disagreement > bars.max_repeat_disagreement:
        problems.append(f"расхождение повторов {stamp.repeat_disagreement:.2f} > "
                        f"{bars.max_repeat_disagreement}")
    return tuple(problems)


def judge_half(run_dir: Path) -> JudgeHalf:
    """The calibration stamp the judge file carries in its first row, the
    MODEL's label counts, and the pre-gate count beside them. No stamp is
    «unknown», which is NOT «calibrated»: spec §8.5 says a report with an
    uncalibrated judge is not circulated."""
    run_id = run_id_of(run_dir)
    path = records.run_file(run_dir, run_id, "<run>.judge.jsonl")
    prompt = str(meta_of(run_dir, run_id).get("prompt_sha256", ""))
    if not path.exists():
        return JudgeHalf(None, {}, 0, calibration_problems(None, prompt))
    rows = records.read_rows(path)
    stamp = records.calibration_stamp_from_json(rows[0]) if rows and "calibrated" in rows[0] else None
    labels: Counter[str] = Counter()
    pregate = 0
    for row in rows[1:] if stamp is not None else rows:
        verdict = records.judge_row_from_json(row).verdict
        if verdict.judged_by == "residual_gate":
            pregate += 1
            continue
        labels[verdict.label] += 1
    return JudgeHalf(stamp=stamp, labels=dict(labels), pregate=pregate,
                     problems=calibration_problems(stamp, prompt))


# --- what the run cost ---------------------------------------------------------------

def _ledger_total(path: Path) -> float | None:
    """The last `cumulative_usd` of a `SpendLedger` file (`bench/agentpii3/
    live/judge.py::SpendLedger.settle` writes one after every charge), or None
    when the run wrote no ledger."""
    if not path.exists():
        return None
    total: float | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("cumulative_usd\t"):
            total = float(line.split("\t")[1])
    return total


def _triple_cost(triple: dict[str, object], path: Path) -> float:
    """One triple's `cost_usd`, refused when it is not a number.

    `float(row.get("cost_usd") or 0.0)` reads a missing field as a free triple,
    which is the same silent zero the whole section exists to avoid: the
    harness writes the key on every triple it produces, including a refused
    one, so its absence means the file is not the file this report thinks."""
    value = triple.get("cost_usd")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReportError(f"{path}: triple {triple.get('case_id')!r} carries no numeric "
                          f"cost_usd ({value!r}) — the price cannot be summed over it")
    return float(value)


def _judge_spend(triple: dict[str, object], path: Path) -> float:
    """What the judge cost on one triple, through `records`' own reader.

    F2.12 / R-54. This used to read `judge_cost_usd` with `.get`, fall back to
    the nested `judge.cost_usd` and then to 0.0 — so a triples file carrying
    neither printed «судья: $0.00», which is also what a run with no judge at
    all prints, and the two are not the same fact. `records.triple_totals_from_
    json` refuses a missing, non-numeric or negative field BY NAME, so the
    reader and `harness.run_triple_v5`'s writer cannot drift apart: the harness
    writes both keys on every triple it produces, including a refused one, and
    their absence means this is not the file the report thinks it is."""
    try:
        return records.triple_totals_from_json(triple).judge_cost_usd
    except records.RecordError as error:
        raise ReportError(f"{path}: тройка {triple.get('case_id')!r} — {error}") from error


def cost_lines(run_dir: Path) -> tuple[str, ...]:
    """Section 0 — what the run cost, from `<run>.triples.jsonl`,
    `<run>.spend.tsv` and `<run>.meta.json`.

    THE DEFINITION IS v4's `bench/agentpii4/harness.py::_cost_lines` and the
    numbers here are its numbers. It is not CALLED because importing
    `bench.agentpii4.harness` imports `bench.agentpii3.live.judge`, which
    imports the engine, and the whole v5 package outside `harness.py` must stay
    free of it (`test_report.test_no_pseudex`). The two extra lines are v5's:
    the ledger's own cumulative total, which is the money that actually left,
    and the judge's spend on its own line instead of parenthesised inside the
    agent's (F2.4).

    A missing file is a PRINTED refusal. «потрачено $0.00» on a run whose
    triples file was never copied reads as a free run."""
    run_id = run_id_of(run_dir)
    triples_path = records.run_file(run_dir, run_id, "<run>.triples.jsonl")
    head = "0. ЦЕНА — измеренная (ResultMessage.total_cost_usd), не оценённая"
    if not triples_path.exists():
        return (head, f"   н/д: нет {triples_path.name} — цена прогона неизвестна")
    triples = records.read_rows(triples_path)
    meta = meta_of(run_dir, run_id)
    complete = [one for one in triples if one.get("status") == "complete"]
    refused = [one for one in triples if one.get("status") == "refused"]
    excluded = [one for one in triples if one.get("status") == "excluded"]
    spent = sum(_triple_cost(one, triples_path) for one in triples)
    judge = sum(_judge_spend(one, triples_path) for one in triples)
    ceiling = meta.get("ceiling_usd")
    out = [head,
           f"   троек: полных {len(complete)} · исключено {len(excluded)} · "
           f"не допущено потолком {len(refused)}",
           f"   потрачено ${spent:.2f} из " + (f"${float(ceiling):.2f}" if isinstance(ceiling, (int, float))
                                               else f"неизвестного потолка (нет {run_id}.meta.json)"),
           f"   судья: ${judge:.2f} — внутри потраченного, не сверх него"]
    ledger = _ledger_total(records.run_file(run_dir, run_id, "<run>.spend.tsv"))
    out.append(f"   журнал {run_id}.spend.tsv: ${ledger:.2f} списано" if ledger is not None
               else f"   журнал трат: нет {run_id}.spend.tsv — списанное не с чем сверить")
    if complete:
        per = sorted(_triple_cost(one, triples_path) for one in complete)
        out.append(f"   тройка: медиана ${per[len(per) // 2]:.4f} · макс ${per[-1]:.4f} · "
                   f"среднее ${sum(per) / len(per):.4f} — потолок на 120 троек × K: "
                   f"${sum(per) / len(per) * 120:.0f} × K")
    verdicts: dict[str, int] = {}
    for one in complete:
        # v4 reads this histogram out of `judge["verdict"]`; `harness.run_
        # triple_v5` writes the same thing under `judge["label"]` (the field
        # name `JudgeVerdict` uses). Reading v4's key on a v5 run would print
        # «— 120» — the shape of a number that is there and means nothing.
        nested = one.get("judge")
        label = str(nested.get("label", "—")) if isinstance(nested, dict) else "—"
        verdicts[label] = verdicts.get(label, 0) + 1
    out.append("   ответ клиенту (плечо I, судья): " + (" · ".join(
        f"{name} {count}" for name, count in sorted(verdicts.items())) or "нет вердиктов"))
    return tuple(out)


# --- the side by side --------------------------------------------------------------------

@dataclass(frozen=True)
class ReportParts:
    """Everything the report is built from, read ONCE from the two directories.

    `side_by_side` and `render` both need v4's two blocks, the observations and
    the judge file; reading them per caller made `report_lines` load the same
    run three times, and the per-behaviour blocks would have made it fourteen."""

    v5_dir: Path
    v4_dir: Path
    v5: RunHalf
    v4: RunHalf
    half: V5Half
    judge: JudgeHalf
    behaviour_of: dict[str, str]
    cost: tuple[str, ...]


def read_parts(v5_run_dir: Path, v4_run_dir: Path) -> ReportParts:
    """Both run directories, read once, in the order a reader would."""
    v5 = v4_half(v5_run_dir, f"v5 run {run_id_of(v5_run_dir)}")
    v4 = v4_half(v4_run_dir, f"v4 baseline {run_id_of(v4_run_dir)}")
    cases = v5_cases(v5_run_dir)
    half = observations_of(v5_run_dir, v5.scored, cases)
    return ReportParts(v5_dir=v5_run_dir, v4_dir=v4_run_dir, v5=v5, v4=v4, half=half,
                       judge=judge_half(v5_run_dir),
                       behaviour_of={case_id: case.behaviour for case_id, case in cases.items()},
                       cost=cost_lines(v5_run_dir))


def _holes(excluded: Sequence[str]) -> tuple[str, ...]:
    """The rows of `SideBySide.excluded_observations` that are HOLES.

    The reason word is `contracts.EXCLUDED_NO_HOPS` and it is read back from
    the row rather than kept in a second field: the `SideBySide` is written to
    `<run>.report.txt` and read by whoever holds it, and two fields that have
    to stay in step are one drift away from a report that prints a hole in one
    section and a clean population in the next."""
    mark = f"({contracts.EXCLUDED_NO_HOPS})"
    return tuple(row for row in excluded if row.endswith(mark))


def _stopped(excluded: Sequence[str]) -> tuple[str, ...]:
    """The complement of `_holes` — the arms that ended in an
    `EXCLUDED_TERMINATION`, each carrying its own termination."""
    mark = f"({contracts.EXCLUDED_NO_HOPS})"
    return tuple(row for row in excluded if not row.endswith(mark))


def assemble(parts: ReportParts, functions: dict[str, Metric]) -> SideBySide:
    """The `SideBySide` of parts already read.

    `functions` is a parameter for the same reason `gate_all` takes one: the
    gate's own test has to be able to register a deliberately broken metric
    under a real name and watch the report refuse it. A report that could only
    ever be built from the real registry is a report nobody has seen go
    «НЕПОЛНЫЙ»."""
    observations = parts.half.observations
    verdicts = gate_all(functions)
    lines: dict[str, Line] = {}
    refused: dict[str, str] = {}
    for name, verdict in verdicts.items():
        if verdict.printable:
            lines[name] = functions[name](observations)
        else:
            refused[name] = verdict.why
    # ONLY the axes a line may be printed on (F2.10). An observation-level line
    # sliced by a HOP axis counts the same answer once per bucket, so the
    # buckets add up to more units than the corpus holds; `metrics.
    # prints_on_axis` is where that rule lives and this loop obeys it instead
    # of restating it. Computing the cells anyway and hiding them at render
    # time would leave a number in the `SideBySide` that nobody may print —
    # and a number that exists gets printed eventually.
    axes: dict[str, dict[str, dict[str, Line]]] = {}
    for name in sorted(lines):
        axes[name] = {axis: {bucket: functions[name](rows)
                             for bucket, rows in sorted(by_axis(observations, axis).items())}
                      for axis in contracts.AXES if prints_on_axis(name, axis)}
    blocked = [name for name in refused if name not in contracts.DIAGNOSTIC_METRIC_NAMES]
    stamp = parts.judge.stamp
    empty_stamp = CalibrationStamp(judge_model="—", prompt_sha256="", n=0, raw_agreement=0.0,
                                   kappa=0.0, per_type_kappa={}, repeat_disagreement=1.0,
                                   calibrated=False)
    # The flag the report prints is the RECOMPUTED one, never the file's: a
    # stamp whose numbers do not clear `contracts.CALIBRATION` says so on every
    # screen it reaches, and the header cannot say «откалиброван» because a row
    # on disk claimed it (finding #7).
    judged = empty_stamp if stamp is None else replace(stamp, calibrated=not parts.judge.problems)
    # ONE list for the two ways the v5 population loses a (case, repeat), with
    # the reason spelled in the row (F2.9). A hole carries `EXCLUDED_NO_HOPS`
    # and is what makes the report НЕПОЛНЫЙ — finding #5 was `residual`
    # printing 1/1 over observations whose hops had never been read; an arm
    # that stopped carries its own termination and does not, because v4's own
    # block already counts it under «исключено» and marking every real run
    # НЕПОЛНЫЙ teaches the reader to scroll past the word.
    excluded = tuple(f"{name} ({contracts.EXCLUDED_NO_HOPS})"
                     for name in parts.half.hopless) + parts.half.stopped
    # `SideBySide` carries NO `v4_extra` (ruling R-35). `v4_leak`,
    # `v4_seed_coverage` and `v4_overmask` are printed by v4's own block,
    # verbatim, a few lines above; re-deriving them here would be a second
    # definition of three numbers that must agree, and two definitions that
    # have to stay equal are one drift away from a report contradicting itself
    # on the same page.
    return SideBySide(
        v5_run=str(parts.v5_dir), v4_run=str(parts.v4_dir),
        corpus_digest_v5=_digest(parts.v5_dir / "corpus.v5.json"),
        corpus_digest_v4=_digest(parts.v4_dir / "corpus.json"),
        agent_model=contracts.AGENT_MODEL, judge=judged,
        v4_levels=level_rows(parts.v5.block), v5_lines=lines, v5_by_axis=axes,
        v5_refused=refused, judge_labels=parts.judge.labels,
        judge_pregate=parts.judge.pregate, excluded_observations=excluded,
        incomplete=bool(blocked) or bool(parts.judge.problems) or bool(_holes(excluded)))


def side_by_side(v5_run_dir: Path, v4_run_dir: Path,
                 functions: dict[str, Metric]) -> SideBySide:
    """Everything the final report prints, from FILES on both sides."""
    return assemble(read_parts(v5_run_dir, v4_run_dir), functions)


def _digest(path: Path) -> str:
    if not path.exists():
        return ""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return str(raw.get("digest", "")) if isinstance(raw, dict) else ""


def behaviour_blocks(half: RunHalf, behaviour_of: dict[str, str]) -> list[str]:
    """v4's own report, once per behaviour, over the triples of that behaviour.

    C-043 / C-046 / C-047: «the agent's logic on substitutes equals the
    control's» was claimed corpus-wide and never for the family that carries
    the claim — `same_tool_other_target`'s `other_person` count, which is the
    whole point of that family, appeared in no table of its own. v4's `render`
    is called on the SUBSET, so the levels, the TOST and the taxonomy of a
    behaviour are computed by the same code as the corpus-wide ones and cannot
    disagree with them about the data."""
    out: list[str] = []
    for behaviour in contracts.BEHAVIOURS:
        ids = {case_id for case_id, name in behaviour_of.items() if name == behaviour}
        if not ids:
            continue
        cases = {case_id: case for case_id, case in half.cases.items() if case_id in ids}
        scored = [one for one in half.scored if one.triple.case_id in ids]
        gone = [one for one in half.excluded if one.split("|")[0] in ids]
        out += ["", f"--- v4 по поведению: {behaviour} ---", ""]
        out += v4_report.render(cases, scored, gone, f"поведение {behaviour}")
    return out


def render(side: SideBySide, parts: ReportParts, dump: int) -> list[str]:
    """The seven sections, in the order the brief fixes them, with the price
    before them (v4 prints it first too) and the report's own holes named."""
    mark = f"  {contracts.INCOMPLETE_REPORT_MARK}" if side.incomplete else ""
    judge = side.judge
    out: list[str] = [
        f"AgentPII-RU v5 — {side.v5_run} против {side.v4_run}{mark}",
        f"агент {side.agent_model} · судья {judge.judge_model} "
        f"(κ={judge.kappa:.2f}, согласие={judge.raw_agreement:.2f}, "
        f"{'откалиброван' if judge.calibrated else 'НЕ ОТКАЛИБРОВАН'}; "
        f"отказано до судьи: {side.judge_pregate})",
        f"корпус v5 {side.corpus_digest_v5[:12] or '—'} · корпус v4 {side.corpus_digest_v4[:12] or '—'}",
        ""]
    out += list(parts.cost)
    out += ["", V4_BLOCK_START, ""]
    out += list(parts.v5.block)
    out += ["", "--- базовый прогон v4 ---", ""]
    out += list(parts.v4.block)
    out += ["", "--- уровни v4: этот прогон рядом с базовым ---",
            "   уровень          сравнимо  I≈C     эффект   TOST"]
    baseline = {row.level: row for row in level_rows(parts.v4.block)}
    for row in side.v4_levels:
        other = baseline.get(row.level)
        out.append(f"   {row.label:16} {row.comparable:5}/{row.triples:<5} "
                   f"{100 * row.agree_ic:6.1f}% {100 * row.effect:+6.1f}pp {row.tost_verdict:15}"
                   + (f" | база {100 * other.agree_ic:6.1f}% {100 * other.effect:+6.1f}pp "
                      f"{other.tost_verdict}" if other is not None else " | базы нет"))
    out += behaviour_blocks(parts.v5, parts.behaviour_of)
    out += ["", V4_BLOCK_END, ""]

    out += ["2. ЛИНИИ v5 — абсолютные доли, интервал Клоппера–Пирсона, «сертифицирует ≥» вместо 100%"]
    # A diagnostic named in `BESIDE` is printed under the line it qualifies and
    # NOT again in the diagnostics block: `out_absent` under `form_hOUT` (F2.10).
    beside_printed: set[str] = set()
    for name in _printing_order(side.v5_lines):
        if name in contracts.DIAGNOSTIC_METRIC_NAMES:
            continue
        out.append("   " + render_line(side.v5_lines[name]))
        companion = BESIDE.get(name)
        if companion is not None and companion in side.v5_lines:
            out.append("   " + render_line(side.v5_lines[companion]))
            beside_printed.add(companion)
    out += ["", "   диагностика — печатается, но не является критерием успеха"]
    for name in _printing_order(side.v5_lines):
        if name in contracts.DIAGNOSTIC_METRIC_NAMES and name not in beside_printed:
            out.append("   " + render_line(side.v5_lines[name]))

    out += ["", "3. ФОРМА И СРЕЗЫ — каждая напечатанная линия по каждой оси; "
                "ось одна за раз, никогда две скрещенные"]
    out += _axis_rows(side)
    for pii_type in contracts.FORM_TYPES:
        counts = {name: count for name, count in differs_histogram(
            parts.half.observations, pii_type).items() if count}
        if counts:
            out.append(f"   расхождения {pii_type}: " + " · ".join(
                f"{name} {count}" for name, count in sorted(counts.items(), key=lambda row: -row[1])))

    out += ["", "4. ЧУВСТВИТЕЛЬНОСТЬ ПО ПОВЕДЕНИЮ — какой эффект семья вообще способна увидеть"]
    for behaviour, rows in sorted(by_axis(parts.half.observations, "behaviour").items()):
        mde = stats.mde_paired(len(rows), MDE_DISCORDANCE, MDE_DEFF)
        out.append(f"   {behaviour:22} n={len(rows):5}  MDE ≈ {100 * mde:5.1f}pp")

    out += ["", "5. СУДЬЯ — метки по восстановленным ответам"]
    out.append("   модель: " + (" · ".join(f"{label} {count}"
                                           for label, count in sorted(side.judge_labels.items()))
                                or "нет вердиктов"))
    # The pre-gate row is SEPARATE and says so. A «неверно» the residual gate
    # decided is not the model's verdict, and folding it into the histogram
    # credits the judge with work it never did (T11).
    out.append(f"   отказано до судьи (подмена стояла в ответе): {side.judge_pregate} — "
               f"решено детерминированно, вне κ")
    for problem in parts.judge.problems:
        out.append(f"   калибровка не принята: {problem}")

    out += ["", "6. ОТКАЗЫ ГЕЙТА — метрики, которые не печатаются, и почему"]
    if side.v5_refused:
        out += [f"   {name}: {why}" for name, why in sorted(side.v5_refused.items())]
    else:
        out.append("   нет")
    # Both counts are read off `side.excluded_observations`, never off the half
    # this report happened to assemble from (F2.9): a `SideBySide` written to a
    # file must still be able to name its own holes.
    holes = _holes(side.excluded_observations)
    stopped = _stopped(side.excluded_observations)
    if holes:
        out.append(f"   НАБЛЮДЕНИЯ ИСКЛЮЧЕНЫ: {len(holes)} — случай объявляет хопы, "
                   f"плечо доиграло, а строк в <run>.hops.jsonl нет: "
                   + " · ".join(holes[:dump]) + (" …" if len(holes) > dump else ""))
    if stopped:
        out.append(f"   плечо не доиграло: {len(stopped)} — наблюдать нечего, "
                   f"v4 считает их в «исключено»: " + " · ".join(stopped[:dump])
                   + (" …" if len(stopped) > dump else ""))

    out += ["", f"7. ПРИМЕРЫ (до {dump} на класс)"]
    out += _examples(parts.half.observations, dump)
    return out


def _axis_rows(side: SideBySide) -> list[str]:
    """Every printed line by every axis of `contracts.AXES`.

    C-080 asks for the slices of §4.2 to be PRINTED; the old report printed
    four axes of two form metrics and the test called `by_axis` itself, so
    every other line's slices existed only in memory. A bucket with no
    applicable observation prints «0/0» rather than being dropped — a slice
    that disappears reads as a slice that was clean."""
    out: list[str] = []
    for name in _printing_order(side.v5_by_axis):
        cells = side.v5_by_axis[name]
        for axis in contracts.AXES:
            # `metrics.prints_on_axis` is the ONE place that says which line may
            # be sliced by which axis; the note is printed instead of the row so
            # the reader sees a rule and not a line that quietly disappeared —
            # a slice that vanishes reads as a slice that was clean (F2.10).
            if not prints_on_axis(name, axis):
                out.append(f"   {name}/{axis}: {AXIS_NOTE}")
                continue
            bucket_lines = cells.get(axis, {})
            out.append(f"   {name}/{axis}: " + (" · ".join(
                f"{bucket} {line.hits}/{line.total}"
                for bucket, line in sorted(bucket_lines.items())) or "н/п"))
    return out


def _printing_order(named: Iterable[str]) -> list[str]:
    """`contracts.METRIC_NAMES` order first, then whatever else the registry
    carried, alphabetically.

    A metric under a name `contracts` does not declare is a finding, not a
    reason to print nothing: the old loop walked METRIC_NAMES and every
    registered line outside it — `rewrite_ratio` and `shared_block` while
    §8.3's rename was landing — silently had no line and no slices at all."""
    names = set(named)
    declared = [name for name in contracts.METRIC_NAMES if name in names]
    return declared + sorted(names - set(contracts.METRIC_NAMES))


def _examples(observations: Sequence[RunObservation], dump: int) -> list[str]:
    buckets: dict[str, list[str]] = {"residual": [], "leaked": [], "differs": []}
    for one in observations:
        for hop in one.hops:
            row = (f"   {hop.case_id}|{hop.repeat} {hop.hop.kind}/{hop.hop.owner} "
                   f"{hop.pii_type} produced={hop.produced!r} reference={hop.reference!r}")
            if hop.status == "residual" and len(buckets["residual"]) < dump:
                buckets["residual"].append(row + "  ДЕФЕКТ ПРОДУКТА — подмена дошла до потребителя")
            elif hop.status == "leaked" and len(buckets["leaked"]) < dump:
                buckets["leaked"].append(row)
            elif (hop.status == "observed" and hop.verdict is not None and hop.verdict.differs
                  and len(buckets["differs"]) < dump):
                buckets["differs"].append(row + f"  differs={sorted(hop.verdict.differs)}")
    out: list[str] = []
    for name, rows in buckets.items():
        out.append(f"   [{name}]")
        out += rows or ["   нет"]
    return out


def report_lines(v5_run_dir: Path, v4_run_dir: Path,
                 functions: dict[str, Metric]) -> list[str]:
    """The whole report, and the two files that prove it was allowed to print."""
    parts = read_parts(v5_run_dir, v4_run_dir)
    side = assemble(parts, functions)
    lines = render(side, parts, dump=8)
    run_id = run_id_of(v5_run_dir)
    records.run_file(v5_run_dir, run_id, "<run>.report.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    records.run_file(v5_run_dir, run_id, "<run>.gate.json").write_text(json.dumps(
        {name: {"printable": verdict.printable, "why": verdict.why}
         for name, verdict in sorted(gate_all(functions).items())},
        ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return lines


def render_side_by_side(v5_run_dir: Path, v4_run_dir: Path) -> list[str]:
    """The report of a real run: the real metric registry, no seam."""
    return report_lines(v5_run_dir, v4_run_dir, METRIC_FUNCTIONS)


# --- the selftest ------------------------------------------------------------------------

# --- the mutation registry -----------------------------------------------------------
# A CONSTANT 1/1 IS THE WEAKEST WITNESS A GATE CAN HAVE, and for one round it
# was the only one: `selftest` broke all 29 metrics the same way, every one
# failed the `zero` fixture BY CONSTRUCTION, and «сломанных отказано: 29 из 29»
# answered nothing. A twenty-mutant sweep written as the implementations each
# ruling replaced found FIVE the fixtures could not tell from the shipped
# metric — and every one of them was a reachable, plausible reading of an
# order, not a typo. The five are registered here, each naming the clause it
# takes away, so the sanction is permanent: a fixture clause deleted tomorrow
# makes `report --selftest` red instead of making a published number quietly
# laxer. C-091 (the checklist row that specified the constant) is updated to
# this shape.
#
# A MUTANT MUST BE NON-EQUIVALENT AND IT MUST BE PLAUSIBLE. These five are the
# previous implementation or the lazy reading of an order, not a random edit:
# an edit no engineer would make proves nothing about the fixtures.


def _mutant_end_to_end(observations: Sequence[RunObservation]) -> Line:
    """`unmasked` counted as a hit — the reading `end_to_end`'s own docstring
    asked for before F1.3 («a passthrough scores 100% here»)."""
    hits = 0
    total = 0
    for one, hop in metric_bodies._owned(observations, "OUT", ("tool_arg",)):
        if not hop.declared:
            continue
        total += 1
        item = metric_bodies._item_of(one, hop.hop.item_id)
        hits += 1 if (hop.status == "unmasked"
                      or (hop.status == "observed" and item is not None
                          and metric_bodies._item_value_ok(hop, item))) else 0
    return Line("end_to_end", hits, total)


def _mutant_out_absent(observations: Sequence[RunObservation]) -> Line:
    """Optional hops dropped from the denominator — «the agent may skip it» read
    as «the benchmark stops counting it»."""
    rows = [hop for _one, hop in metric_bodies._hops(observations, "OUT")
            if hop.declared and not hop.hop.optional]
    return Line("out_absent", sum(1 for hop in rows if hop.status == "absent"), len(rows))


def _mutant_consistency(observations: Sequence[RunObservation]) -> Line:
    """Population keyed on `MentionRecord.msg` alone, so every tool result is
    ONE place however many results printed the value — the reading that left
    the line with an empty population on the whole corpus."""
    hits = 0
    total = 0
    for one in observations:
        for item in one.case.base.pii:
            mentions = metric_bodies._mentions_of(one, item.id)
            if len({mention.msg for mention in mentions}) < 2:
                continue
            total += 1
            hits += 1 if len({mention.substitute for mention in mentions}) == 1 else 0
    return Line("consistency", hits, total)


def _mutant_doc_extracted(observations: Sequence[RunObservation]) -> Line:
    """«Did A real value of the case arrive» instead of «did THIS item's»: the
    shuffled-CSV failure, scored as a success."""
    hits = 0
    total = 0
    for one in observations:
        if one.case.document is None:
            continue
        for item_id in one.case.document.extracted_item_ids:
            total += 1
            hop = next((other for other in one.hops
                        if other.declared and other.hop.kind == "OUT"
                        and other.hop.item_id == item_id), None)
            arrived = hop is not None and hop.status == "observed" and any(
                metric_bodies.value_matches(item.type, hop.produced, item.canonical)
                for item in one.case.base.pii)
            hits += 1 if arrived else 0
    return Line("doc_extracted", hits, total)


def _mutant_form_hIN(observations: Sequence[RunObservation]) -> Line:  # noqa: N802 - metric name
    """A LEAKED hop counted as a form hit — the value the gateway never touched
    paying for the axis that measures what it did touch."""
    rows = [hop for _one, hop in metric_bodies._hops(observations, "IN")
            if hop.status in ("observed", "leaked")]
    return Line("form_hIN", sum(1 for hop in rows
                                if hop.status == "leaked"
                                or (hop.verdict is not None and hop.verdict.same)), len(rows))


MUTANTS: tuple[tuple[str, str, Metric], ...] = (
    ("end_to_end", "`unmasked` leaf is a HIT (the pre-F1.3 reading)", _mutant_end_to_end),
    ("out_absent", "optional hops dropped from the denominator", _mutant_out_absent),
    ("consistency", "a tool result is not a place: population keyed on `msg` alone", _mutant_consistency),
    ("doc_extracted", "any real value of the case counts, not THIS item's", _mutant_doc_extracted),
    ("form_hIN", "a leaked hop is a form hit", _mutant_form_hIN),
)


def selftest() -> int:
    """Break every metric and demand a red for each, then run the real ones and
    demand a green for each. The shape of `e2e/audit_gates.py --selftest`: a
    gate nobody has watched fail is a gate that has never been shown to work.

    TWO SWEEPS, AND THE SECOND IS THE ONE THAT MEANS SOMETHING. The constant
    `Line(name, 1, 1)` fails every `zero` fixture by construction; the
    registered mutants are the implementations the rulings replaced, and each
    one PASSED this gate until the fixture clause beside it was written."""
    broken: dict[str, Metric] = {
        name: (lambda _observations, _name=name: Line(_name, 1, 1)) for name in METRIC_FUNCTIONS}
    failures: list[str] = []
    for name, verdict in gate_all(broken).items():
        if verdict.printable:
            failures.append(f"{name}: постоянная метрика 1/1 прошла гейт — гейт не может покраснеть")
    survivors: list[str] = []
    for name, label, mutant in MUTANTS:
        fixtures = FIXTURES.get(name)
        if not fixtures:
            survivors.append(f"{name}: мутант «{label}» не с чем сверить — нет фикстур")
            continue
        if gate(mutant, fixtures).printable:
            survivors.append(f"{name}: мутант «{label}» прошёл гейт — не хватает пункта в фикстуре")
    failures.extend(survivors)
    for name, verdict in gate_all(METRIC_FUNCTIONS).items():
        if not verdict.printable:
            failures.append(f"{name}: настоящая метрика отказана — {verdict.why}")
    passed_broken = sum(1 for one in failures if "постоянная" in one)
    print(f"  сломанных отказано: {len(METRIC_FUNCTIONS) - passed_broken} из {len(METRIC_FUNCTIONS)}")
    print(f"  мутантов отказано: {len(MUTANTS) - len(survivors)} из {len(MUTANTS)}")
    print("report --selftest: PASS" if not failures
          else "report --selftest: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("v5_run", nargs="?", type=Path)
    parser.add_argument("v4_run", nargs="?", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.v5_run is None or args.v4_run is None:
        parser.error("нужны два каталога прогонов, или --selftest")
    for line in render_side_by_side(args.v5_run, args.v4_run):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
