"""The gate that refuses to print, and the report it lets through.

TWO JOBS, AND THE FIRST ONE IS THE PRODUCT.

  1. `gate` / `gate_all` — every metric runs its three fixtures (`fixtures.py`)
     and must print exactly the fraction each one declares, with the `zero`
     fixture at 0.0 and the `one` fixture at 1.0. A metric that fails any of
     that is NOT PRINTED; its name and the reason go to `v5_refused`, and a
     report holding a refused NON-diagnostic metric carries
     `contracts.INCOMPLETE_REPORT_MARK` in its header. Not printing is the only
     sanction that survives a deadline — a warning gets read once and then
     scrolled past, a missing number gets asked about.
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
the sentence a reader would take as a TOST result.

Run:  python3 -m bench.agentpii5.report --selftest
      python3 -m bench.agentpii5.report <v5-run-dir> <v4-run-dir>
"""
import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from bench.agentpii4 import report as v4_report
from bench.agentpii4 import stats
from bench.agentpii4.autopsy import _load_run
from bench.agentpii4.report import Scored
from bench.agentpii5 import contracts, records
from bench.agentpii5.contracts import (
    CalibrationStamp,
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
from bench.agentpii5.metrics import METRIC_FUNCTIONS, by_axis
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
# v4 prints one level line per level; this reads them back rather than
# recomputing, so the two halves of the report cannot disagree about the data.
_LEVEL_LINE = re.compile(
    r"^\s+(?P<comparable>\d+)/(?P<triples>\d+)\s+"
    r"(?P<ic>[\d.]+%|n/a)\s+(?P<cc>[\d.]+%|n/a)\s+"
    r"(?P<effect>[+-][\d.]+)pp\s+\[\s*(?P<lo>[+-][\d.]+),\s*(?P<hi>[+-][\d.]+)\]\s+"
    r"(?P<verdict>\S+)\s+\[\s*(?P<tl>[+-][\d.]+),\s*(?P<th>[+-][\d.]+)\]\s+"
    r"(?P<p>[\d.]+)\s+\((?P<b>\d+),(?P<c>\d+)\)\s+"
    r"(?P<icc_case>[-\d.]+)\s+(?P<icc_value>[-\d.]+)\s+(?P<deff>[\d.]+)\s*$")


class ReportError(ValueError):
    """A run directory that cannot be read as a run. Raised with the path and
    the missing file: a report built from half a run would be a report about
    whichever half happened to be there."""


# --- the gate --------------------------------------------------------------------------

def gate(metric: Metric, fixtures: Sequence[Fixture]) -> GateVerdict:
    """One metric against its three fixtures. NEVER raises on a wrong metric —
    a wrong metric is the finding, and a gate that crashed on it would take the
    whole report down instead of printing the one line that matters."""
    name = fixtures[0].metric if fixtures else "?"
    kinds = {fixture.kind for fixture in fixtures}
    missing = [kind for kind in contracts.FIXTURE_KINDS if kind not in kinds]
    if missing:
        return GateVerdict(name, False, f"нет фикстур: {', '.join(missing)}")
    seen: dict[str, float] = {}
    for fixture in fixtures:
        try:
            line = metric(fixture.input)
        except Exception as error:  # noqa: BLE001 - the exception IS the verdict
            return GateVerdict(name, False, f"{fixture.name}: метрика упала — {error!r}")
        if (line.hits, line.total) != (fixture.expected_hits, fixture.expected_total):
            return GateVerdict(name, False, f"{fixture.name}: напечатала {line.hits}/{line.total}, "
                                            f"ждали {fixture.expected_hits}/{fixture.expected_total}")
        seen[fixture.kind] = line.rate
    if seen["one"] - seen["zero"] < contracts.FIXTURE_MIN_SEPARATION:
        return GateVerdict(name, False, f"не разделяет: zero {seen['zero']:.2f}, one {seen['one']:.2f} "
                                        f"(нужно ≥ {contracts.FIXTURE_MIN_SEPARATION})")
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


def v4_half(run_dir: Path, header: str) -> tuple[list[str], list[Scored], dict[str, object]]:
    """v4's own report of a run, and the scored triples behind it.

    Produced by v4's `_load_run` → `score_triples` → `render`, in that order and
    with no v5 argument anywhere: this is the baseline, and the baseline must
    not know it is being compared."""
    cases, triples, excluded = _load_run(run_dir)
    scored = v4_report.score_triples(cases, triples)
    return v4_report.render(cases, scored, excluded, header), scored, dict(cases)


def level_rows(block: list[str]) -> tuple[LevelRow, ...]:
    """v4's level lines, parsed back into fields. Read from the printed text on
    purpose — the side-by-side then cannot show a number the v4 block does not."""
    out: list[LevelRow] = []
    for level, label in contracts.V4_LEVELS:
        line = next((one for one in block if one.startswith("   " + label)), None)
        if line is None:
            continue
        hit = _LEVEL_LINE.match(line[len("   " + label):])
        if hit is None:
            continue
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


def v5_observations(run_dir: Path, scored: Sequence[Scored]) -> list[RunObservation]:
    """Rebuild the `RunObservation`s of a v5 run from its files.

    The hops are READ, never recomputed: `observe.py` ran once, during the run,
    on records that are now on disk beside its output, and a report that
    re-derived them could print numbers no run ever produced."""
    run_id = run_id_of(run_dir)
    corpus_path = run_dir / "corpus.v5.json"
    if not corpus_path.exists():
        raise ReportError(f"{run_dir}: no corpus.v5.json — a v5 report needs the v5 corpus")
    # Keyed by the BASE case id: `case_v5_to_json` nests the v4 case under
    # "base" so the two corpus files carry the same bytes for the v4 half, and
    # reading the id off the outer row would key every case under None.
    loaded = [case_v5_from_json(row)
              for row in json.loads(corpus_path.read_text(encoding="utf-8"))["corpus"]]
    cases = {case.base.id: case for case in loaded}
    hops: dict[tuple[str, int], list[HopObservation]] = {}
    hops_path = records.run_file(run_dir, run_id, "<run>.hops.jsonl")
    for row in records.read_rows(hops_path) if hops_path.exists() else []:
        one = records.hop_observation_from_json(row)
        hops.setdefault((one.case_id, one.repeat), []).append(one)
    pairs = {(item.triple.case_id, item.triple.repeat): (item.ic, item.cc) for item in scored}
    out: list[RunObservation] = []
    for row in records.merged_v5_records(run_dir):
        run = records.arm_v5_from_record(row)
        case = cases.get(run.base.case_id)
        if case is None:
            raise ReportError(f"{run_dir}: arm record for {run.base.case_id!r} has no v5 case in "
                              f"corpus.v5.json; the run and its corpus are not the same run")
        ic, cc = pairs.get((run.base.case_id, run.base.repeat), (None, None))
        out.append(RunObservation(case=case, repeat=run.base.repeat,
                                  hops=tuple(hops.get((run.base.case_id, run.base.repeat), ())),
                                  run=run, ic=ic, cc=cc))
    return out


def judge_half(run_dir: Path) -> tuple[CalibrationStamp | None, dict[str, int]]:
    """The calibration stamp the judge file carries in its first row, and the
    label counts behind it. No stamp is «unknown», which is NOT «calibrated»:
    spec §8.5 says a report with an uncalibrated judge is not circulated."""
    run_id = run_id_of(run_dir)
    path = records.run_file(run_dir, run_id, "<run>.judge.jsonl")
    if not path.exists():
        return None, {}
    rows = records.read_rows(path)
    stamp = records.calibration_stamp_from_json(rows[0]) if rows and "calibrated" in rows[0] else None
    labels: Counter[str] = Counter()
    for row in rows[1:] if stamp is not None else rows:
        labels[records.judge_row_from_json(row).verdict.label] += 1
    return stamp, dict(labels)


# --- the side by side --------------------------------------------------------------------

def side_by_side(v5_run_dir: Path, v4_run_dir: Path,
                 functions: dict[str, Metric]) -> SideBySide:
    """Everything the final report prints, from FILES on both sides.

    `functions` is a parameter for the same reason `gate_all` takes one: the
    gate's own test has to be able to register a deliberately broken metric
    under a real name and watch the report refuse it. A report that could only
    ever be built from the real registry is a report nobody has seen go
    «НЕПОЛНЫЙ»."""
    v5_block, v5_scored, _v5_cases = v4_half(v5_run_dir, f"v5 run {run_id_of(v5_run_dir)}")
    v4_block, _v4_scored, _v4_cases = v4_half(v4_run_dir, f"v4 baseline {run_id_of(v4_run_dir)}")
    observations = v5_observations(v5_run_dir, v5_scored)
    verdicts = gate_all(functions)
    lines: dict[str, Line] = {}
    refused: dict[str, str] = {}
    for name, verdict in verdicts.items():
        if verdict.printable:
            lines[name] = functions[name](observations)
        else:
            refused[name] = verdict.why
    axes: dict[str, dict[str, dict[str, Line]]] = {}
    for name in sorted(lines):
        axes[name] = {axis: {bucket: functions[name](rows)
                             for bucket, rows in sorted(by_axis(observations, axis).items())}
                      for axis in contracts.AXES}
    stamp, labels = judge_half(v5_run_dir)
    blocked = [name for name in refused if name not in contracts.DIAGNOSTIC_METRIC_NAMES]
    empty_stamp = CalibrationStamp(judge_model="—", prompt_sha256="", n=0, raw_agreement=0.0,
                                   kappa=0.0, per_type_kappa={}, repeat_disagreement=1.0,
                                   calibrated=False)
    # `SideBySide` carries NO `v4_extra` (ruling R-35). `v4_leak`,
    # `v4_seed_coverage` and `v4_overmask` are printed by v4's own block,
    # verbatim, a few lines above; re-deriving them here would be a second
    # definition of three numbers that must agree, and two definitions that
    # have to stay equal are one drift away from a report contradicting itself
    # on the same page.
    side = SideBySide(
        v5_run=str(v5_run_dir), v4_run=str(v4_run_dir),
        corpus_digest_v5=_digest(v5_run_dir / "corpus.v5.json"),
        corpus_digest_v4=_digest(v4_run_dir / "corpus.json"),
        agent_model=contracts.AGENT_MODEL, judge=stamp if stamp is not None else empty_stamp,
        v4_levels=level_rows(v5_block), v5_lines=lines, v5_by_axis=axes,
        v5_refused=refused, judge_labels=labels,
        incomplete=bool(blocked) or stamp is None or not stamp.calibrated)
    return side


def _digest(path: Path) -> str:
    if not path.exists():
        return ""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return str(raw.get("digest", "")) if isinstance(raw, dict) else ""


def render(side: SideBySide, v5_block: list[str], v4_block: list[str],
           observations: Sequence[RunObservation], dump: int) -> list[str]:
    """The seven sections, in the order the brief fixes them."""
    mark = f"  {contracts.INCOMPLETE_REPORT_MARK}" if side.incomplete else ""
    out: list[str] = [
        f"AgentPII-RU v5 — {side.v5_run} против {side.v4_run}{mark}",
        f"агент {side.agent_model} · судья {side.judge.judge_model} "
        f"(κ={side.judge.kappa:.2f}, согласие={side.judge.raw_agreement:.2f}, "
        f"{'откалиброван' if side.judge.calibrated else 'НЕ ОТКАЛИБРОВАН'})",
        f"корпус v5 {side.corpus_digest_v5[:12] or '—'} · корпус v4 {side.corpus_digest_v4[:12] or '—'}",
        "",
        V4_BLOCK_START, ""]
    out += v5_block
    out += ["", "--- базовый прогон v4 ---", ""]
    out += v4_block
    out += ["", "--- уровни v4: этот прогон рядом с базовым ---",
            "   уровень          сравнимо  I≈C     эффект   TOST"]
    baseline = {row.level: row for row in level_rows(v4_block)}
    for row in side.v4_levels:
        other = baseline.get(row.level)
        out.append(f"   {row.label:16} {row.comparable:5}/{row.triples:<5} "
                   f"{100 * row.agree_ic:6.1f}% {100 * row.effect:+6.1f}pp {row.tost_verdict:15}"
                   + (f" | база {100 * other.agree_ic:6.1f}% {100 * other.effect:+6.1f}pp "
                      f"{other.tost_verdict}" if other is not None else " | базы нет"))
    out += ["", V4_BLOCK_END, ""]

    out += ["2. ЛИНИИ v5 — абсолютные доли, интервал Клоппера–Пирсона, «сертифицирует ≥» вместо 100%"]
    for name in contracts.METRIC_NAMES:
        if name in side.v5_lines and name not in contracts.DIAGNOSTIC_METRIC_NAMES:
            out.append("   " + render_line(side.v5_lines[name]))
    out += ["", "   диагностика — печатается, но не является критерием успеха"]
    for name in contracts.DIAGNOSTIC_METRIC_NAMES:
        if name in side.v5_lines:
            out.append("   " + render_line(side.v5_lines[name]))

    out += ["", "3. ФОРМА — по типу, по владельцу хопа, по вертикали, по поведению"]
    for metric in ("form_hIN", "form_hOUT"):
        if metric not in side.v5_by_axis:
            continue
        for axis in ("pii_type", "hop_owner", "vertical", "behaviour"):
            cells = side.v5_by_axis[metric].get(axis, {})
            out.append(f"   {metric}/{axis}: " + " · ".join(
                f"{bucket} {line.hits}/{line.total}" for bucket, line in sorted(cells.items())))
    for pii_type in contracts.FORM_TYPES:
        counts = {name: count for name, count in differs_histogram(observations, pii_type).items() if count}
        if counts:
            out.append(f"   расхождения {pii_type}: " + " · ".join(
                f"{name} {count}" for name, count in sorted(counts.items(), key=lambda row: -row[1])))

    out += ["", "4. ЧУВСТВИТЕЛЬНОСТЬ ПО ПОВЕДЕНИЮ — какой эффект семья вообще способна увидеть"]
    for behaviour, rows in sorted(by_axis(observations, "behaviour").items()):
        mde = stats.mde_paired(len(rows), MDE_DISCORDANCE, MDE_DEFF)
        out.append(f"   {behaviour:22} n={len(rows):5}  MDE ≈ {100 * mde:5.1f}pp")

    out += ["", "5. СУДЬЯ — метки по восстановленным ответам"]
    out.append("   " + (" · ".join(f"{label} {count}" for label, count in sorted(side.judge_labels.items()))
                        or "нет вердиктов"))

    out += ["", "6. ОТКАЗЫ ГЕЙТА — метрики, которые не печатаются, и почему"]
    if side.v5_refused:
        out += [f"   {name}: {why}" for name, why in sorted(side.v5_refused.items())]
    else:
        out.append("   нет")

    out += ["", f"7. ПРИМЕРЫ (до {dump} на класс)"]
    out += _examples(observations, dump)
    return out


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
    v5_block, v5_scored, _cases = v4_half(v5_run_dir, f"v5 run {run_id_of(v5_run_dir)}")
    v4_block, _v4_scored, _v4_cases = v4_half(v4_run_dir, f"v4 baseline {run_id_of(v4_run_dir)}")
    side = side_by_side(v5_run_dir, v4_run_dir, functions)
    observations = v5_observations(v5_run_dir, v5_scored)
    lines = render(side, v5_block, v4_block, observations, dump=8)
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

def selftest() -> int:
    """Break every metric in the same way and demand a red for each, then run
    the real ones and demand a green for each. The shape of
    `e2e/audit_gates.py --selftest`: a gate nobody has watched fail is a gate
    that has never been shown to work."""
    broken: dict[str, Metric] = {
        name: (lambda _observations, _name=name: Line(_name, 1, 1)) for name in METRIC_FUNCTIONS}
    failures: list[str] = []
    for name, verdict in gate_all(broken).items():
        if verdict.printable:
            failures.append(f"{name}: постоянная метрика 1/1 прошла гейт — гейт не может покраснеть")
    for name, verdict in gate_all(METRIC_FUNCTIONS).items():
        if not verdict.printable:
            failures.append(f"{name}: настоящая метрика отказана — {verdict.why}")
    passed_broken = sum(1 for one in failures if "постоянная" in one)
    print(f"  сломанных отказано: {len(METRIC_FUNCTIONS) - passed_broken} из {len(METRIC_FUNCTIONS)}")
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
