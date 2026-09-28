"""M04 integration — the PRODUCED report path is the frozen, engine-free one.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_report_frozen          # ~10 s

WHY THIS FILE EXISTS BESIDE `test_frozen_oracle.py`. That file proves the ORACLE
is engine-free in isolation. This one proves the WIRING: the report the product
actually prints (`report.render_side_by_side`, the function `harness.finish_run`
calls) gets its v5 lines from that oracle, and the report path does not reach the
mutable engine to produce them.

FOUR FACTS, ONE PER CHECK (plus the two added later, each its own sentence):

  * `real_report_prints_the_frozen_lines` — on a real saved run directory, every
    v5 line `assemble` publishes is byte-equal to the frozen score's line. The
    unit test cannot see an orphan; this one reads the directory the way
    `harness.finish_run` does.
  * `removing_the_wiring_turns_the_check_red` — the MUTATION. Tamper the frozen
    score and the printed line must follow it. If the wiring were removed (the
    line recomputed from `metrics` beside the oracle), the printed line would be
    the metric's own value and this check goes red. A test that cannot fail when
    the wiring is deleted certifies nothing.
  * `the_report_does_not_destroy_the_callers_engine` — the report runs at the END
    of a live harness process that already holds the engine. An oracle that
    UNLOADS `pseudex` from `sys.modules` to produce its number mutates its
    caller: the next lazy import in that process builds a SECOND copy of the
    engine. Engine-free means «the score needs no engine», not «the process may
    not have one».
  * `poisoned_register_spelling_leaves_the_score_bytes_identical` — the sentence
    the M04 row is written about, at the level of the produced lines AND their
    axis slices: with `pseudex.address` poisoned so that any attribute read
    raises, the same saved run yields the same bytes.
  * `published_lines_and_slices_score_the_saved_population` — OBS: on a run with
    one case's saved hops removed, every published total equals the same metric
    over the SAVED half, the axis buckets reconcile with it, the report stays
    НЕПОЛНЫЙ, and the digest covers the hops it scored (so removing them moves
    it).
  * `production_capture_persists_a_versioned_table` — the repair witness is
    captured ONCE at run production, persisted beside the run and READ (never
    re-asked) by the scorer.

WHAT IS OUT OF SCOPE HERE. v4's own block (`parts.v5.block`, `parts.v4.block`,
the per-behaviour blocks) is v4's own instrument, rendered by
`bench.agentpii4.report.render`, and it reaches `pseudex.address.
register_spelling` by design. That is v4's baseline and this file does not claim
it for the frozen oracle: M04 freezes the v5 SCORE, and the v5 score is what
these checks read.
"""
from __future__ import annotations

import pathlib
import sys
from collections.abc import Callable
from dataclasses import replace

from bench.agentpii5 import frozen_oracle, metrics, report as report_mod, test_report
from bench.agentpii5.contracts import Line


class Poison:
    """Any attribute read from the poisoned engine is a failure, not a value."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"the report reached the engine: pseudex.{name}")


def _run_pair(tmp: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """A real v5 run directory and its v4 baseline, written to disk the way the
    harness writes them — so every check scores FILES and not live objects."""
    v5 = test_report.build_run(tmp, test_report.RUN_ID, True)
    v4 = test_report.build_run(tmp, "baseline01", False)
    return v5, v4


def _run_with_a_missing_case(tmp: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """The synthetic fixture with ONE case's saved hops removed.

    A copy of the existing fixture, not a second one: the defect only exists
    when the saved hops and the saved arm rows disagree, and a hand-built
    fixture would not be the run `harness.finish_run` writes. The mutation is
    the exact one `test_report._drop_hops` uses for finding #5 — a run that died
    between the arm write and the hop write."""
    v5, v4 = _run_pair(tmp)
    test_report._drop_hops(v5, test_report.FIXTURE_BEHAVIOURS[1][0])
    return v5, v4


def _poison(prefix_modules: tuple[str, ...] = ("pseudex", "pseudex.address",
                                               "pseudex.detect_all")) -> dict[str, object]:
    """Replace the engine in `sys.modules` with `Poison`; return what to restore."""
    saved = {name: sys.modules[name] for name in list(sys.modules)
             if name == "pseudex" or name.startswith("pseudex.")}
    for name in saved:
        del sys.modules[name]
    for name in prefix_modules:
        sys.modules[name] = Poison()  # type: ignore[assignment]
    return saved


def _unpoison(saved: dict[str, object], prefix_modules: tuple[str, ...]) -> None:
    for name in prefix_modules:
        sys.modules.pop(name, None)
    sys.modules.update(saved)  # type: ignore[arg-type]


# --- checks ---------------------------------------------------------------------------

def test_real_report_prints_the_frozen_lines() -> list[str]:
    """THE WIRING SENTENCE: every line the produced report publishes is the line
    the frozen score already computed from the rows on disk."""
    import tempfile
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5, v4 = _run_pair(pathlib.Path(tmp))
        parts = report_mod.read_parts(v5, v4)
        side = report_mod.assemble(parts, metrics.METRIC_FUNCTIONS)
    if not report_mod.frozen_oracle.FROZEN_ORACLE_VERSION:
        problems.append("the frozen oracle carries no version")
    if parts.frozen.oracle_version != frozen_oracle.FROZEN_ORACLE_VERSION:
        problems.append(f"the report names oracle {parts.frozen.oracle_version!r}, not the "
                        f"current {frozen_oracle.FROZEN_ORACLE_VERSION!r}")
    if not parts.frozen.digest:
        problems.append("the report carries no artifact digest")
    shared = [name for name in side.v5_lines if name in parts.frozen.lines]
    if not shared:
        problems.append("the produced report printed no frozen line — the oracle is an orphan")
    for name in shared:
        if side.v5_lines[name] != parts.frozen.lines[name]:
            problems.append(f"{name}: the report printed {side.v5_lines[name]}, the frozen "
                            f"score has {parts.frozen.lines[name]}")
    return problems


def test_removing_the_wiring_turns_the_check_red() -> list[str]:
    """THE MUTATION. Tamper the frozen score; the PRODUCED line must move with it.

    A wiring that cannot be told from no wiring is not a wiring: if `assemble`
    recomputed the line from `metrics` beside the oracle, the sentinel would
    never appear and this check fails."""
    import tempfile
    problems: list[str] = []
    sentinel_hits, sentinel_total = 1234, 5678
    with tempfile.TemporaryDirectory() as tmp:
        v5, v4 = _run_pair(pathlib.Path(tmp))
        parts = report_mod.read_parts(v5, v4)
        printed = report_mod.assemble(parts, metrics.METRIC_FUNCTIONS)
        tampered_lines = {name: Line(name, sentinel_hits, sentinel_total)
                          for name in parts.frozen.lines}
        tampered = replace(parts, frozen=replace(parts.frozen, lines=tampered_lines))
        mutated = report_mod.assemble(tampered, metrics.METRIC_FUNCTIONS)
    shared = [name for name in mutated.v5_lines if name in tampered_lines]
    if not shared:
        return ["the mutation printed no line the frozen score carries — nothing to observe"]
    for name in shared:
        line = mutated.v5_lines[name]
        if (line.hits, line.total) != (sentinel_hits, sentinel_total):
            problems.append(f"{name}: the printed line ignored the frozen score "
                            f"({line.hits}/{line.total}, the sentinel was "
                            f"{sentinel_hits}/{sentinel_total}) — the wiring is absent")
        if printed.v5_lines.get(name) == line:
            problems.append(f"{name}: tampering the frozen score changed nothing — the "
                            f"printed line does not come from it")
    return problems


def test_the_report_does_not_destroy_the_callers_engine() -> list[str]:
    """ENGINE-FREE IS NOT «UNLOAD THE CALLER». The live harness that calls this
    report has already imported the engine; a report that pops `pseudex` out of
    `sys.modules` to score leaves its caller with stale module objects and a
    second copy on the next lazy import."""
    import importlib
    import tempfile
    problems: list[str] = []
    importlib.import_module("pseudex.address")
    if "pseudex.address" not in sys.modules:
        return ["pseudex.address did not import in this environment — the check is vacuous"]
    with tempfile.TemporaryDirectory() as tmp:
        v5, v4 = _run_pair(pathlib.Path(tmp))
        report_mod.read_parts(v5, v4)
    for name in ("pseudex", "pseudex.address"):
        if name not in sys.modules:
            problems.append(f"the report removed {name!r} from the caller's process; a "
                            f"report may not unload the engine to score")
    return problems


def test_poisoned_register_spelling_leaves_the_score_bytes_identical() -> list[str]:
    """The M04 sentence at the PRODUCED level: same saved run, same frozen lines
    and same axis slices, with the engine poisoned so any attribute read raises."""
    import tempfile
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        v5, _v4 = _run_pair(pathlib.Path(tmp))
        first = report_mod.frozen_score_and_observations(v5)
        first_cells = report_mod.axis_cells(first.half.observations, metrics.METRIC_FUNCTIONS,
                                            first.frozen.lines)
        saved = _poison()
        try:
            second = report_mod.frozen_score_and_observations(v5)
            second_cells = report_mod.axis_cells(second.half.observations,
                                                 metrics.METRIC_FUNCTIONS, second.frozen.lines)
        finally:
            _unpoison(saved, ("pseudex", "pseudex.address", "pseudex.detect_all"))
    if first.frozen.digest != second.frozen.digest:
        problems.append(f"the digest moved under poisoning: {first.frozen.digest} → "
                        f"{second.frozen.digest}")
    for name in sorted(set(first.frozen.lines) | set(second.frozen.lines)):
        if first.frozen.lines.get(name) != second.frozen.lines.get(name):
            problems.append(f"{name}: {first.frozen.lines.get(name)} with the engine, "
                            f"{second.frozen.lines.get(name)} with it poisoned")
    for name in sorted(set(first_cells) | set(second_cells)):
        if first_cells.get(name) != second_cells.get(name):
            problems.append(f"{name}: the axis slices moved under poisoning")
    return problems


def test_production_capture_persists_a_versioned_table() -> list[str]:
    """THE REPAIR WITNESS IS CAPTURED ONCE, AT RUN PRODUCTION, AND PERSISTED.

    A pair the run actually produced is frozen with the engine's own rule (here a
    stub `spell`, since this check is about the DATA and not the engine), written
    beside the run, read back by the report, and counted as MEASURED — while a
    run with no captured table stays UNMEASURED and is never printed clean. The
    corpus is the REAL one because a fixture corpus carries no repaired LOC pair
    and a vacuous capture check is not a check."""
    import json
    import tempfile
    from bench.agentpii4.records import ArmMeta
    from bench.agentpii5 import observe, perfect
    from bench.agentpii5.schema import case_v5_to_json
    problems: list[str] = []
    meta = ArmMeta(model="capture-test", turns=1, duration_ms=0, session_id="",
                   subtype="", is_error=False, api_error_status=None, errors=(),
                   reason="", cap_usd=0.0)
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp) / "capture01"
        run_dir.mkdir(parents=True)
        cases = perfect.cases_of_tier(perfect.load_cases(perfect.CORPUS_PATH),
                                      perfect.load_ladder(perfect.LADDER_PATH), "nano")
        (run_dir / "corpus.v5.json").write_text(json.dumps(
            {"corpus": [case_v5_to_json(case) for case in cases], "digest": "capture"},
            ensure_ascii=False), encoding="utf-8")
        written_observations = []
        for case in cases:
            run = perfect.simulate(case)
            report_mod.records.append_row(
                report_mod.records.run_file(run_dir, "capture01", "<run>.arms.v5.jsonl"),
                report_mod.records.arm_v5_record(run, meta, case.base))
            observation = observe.observe(case, run, None, None)
            written_observations.append(observation)
            for hop in observation.hops:
                report_mod.records.append_row(
                    report_mod.records.run_file(run_dir, "capture01", "<run>.hops.jsonl"),
                    report_mod.records.hop_observation_to_json(hop))
        pairs = frozen_oracle.repair_pairs(tuple(written_observations))
        if not pairs:
            return ["the nano tier produced no LOC pair — the capture check measured nothing"]
        written = frozen_oracle.capture_run_repairs(run_dir, pairs, lambda word: word.lower())
        if written != frozen_oracle.repairs_path(run_dir):
            problems.append(f"the witnesses went to {written}, not the run's repairs path")
        table = frozen_oracle.read_repairs(run_dir)
        if len(table.witnesses) != len(pairs):
            problems.append(f"{len(pairs)} pairs captured, {len(table.witnesses)} witnesses on disk")
        payload = frozen_oracle.repairs_path(run_dir).read_text(encoding="utf-8")
        if frozen_oracle.FROZEN_ORACLE_VERSION not in payload:
            problems.append("the persisted table names no oracle version")
        scored = frozen_oracle.score_artifacts(report_mod.v5_corpus(run_dir),
                                               report_mod.records.merged_v5_records(run_dir), table)
        if scored.repairs_measured != len(pairs):
            problems.append(f"{scored.repairs_measured} of {len(pairs)} captured pairs came back "
                            f"measured — the report did not read its own table")
        if scored.repairs_unmeasured:
            problems.append(f"{scored.repairs_unmeasured} pairs still unmeasured after capture")
    return problems


def test_published_lines_and_slices_score_the_saved_population() -> list[str]:
    """OBS — THE PUBLISHED TOTALS, THEIR SLICES AND THE DIGEST SCORE ONE SAVED
    POPULATION, and a run whose hops are incomplete never claims otherwise.

    THE DEFECT. `frozen_score_and_observations` produced `frozen.lines` by
    `frozen_oracle.score_artifacts(corpus, rows, repairs)`, which RE-DERIVES
    every hop with `observe.observe`; the published axis slices
    (`assemble` → `axis_cells`) and the report's own population were built from
    the SAVED `<run>.hops.jsonl`. On a saved run with one case's hops absent the
    totals counted a case the slices could not — one page, two populations —
    and the versioned digest, taken over (corpus ids, rows) alone, could not see
    the hops it had scored, so a run whose hops changed kept one address.

    THE FOUR SENTENCES THIS CHECK HOLDS, on a copy of the synthetic fixture with
    one case's saved hops removed:

      * every PUBLISHED line's (hits, total) equals the same metric over
        `parts.half.observations` — the saved population the report slices;
      * the axis buckets of every printed line reconcile with that line's total,
        so a slice cannot be counted from another population;
      * the report of a run with a hole is marked incomplete — the fix must not
        buy coherence by pretending the missing case was scored;
      * the digest MOVES when the scored hops move, because it names them.

    NO FIXTURE LITERAL IS ADDED: the one case id used is read off
    `test_report.FIXTURE_BEHAVIOURS`, and no PII value appears here."""
    import tempfile
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        v5, v4 = _run_with_a_missing_case(root)
        complete = report_mod.frozen_score_and_observations(
            test_report.build_run(root, "complete01", True))
        parts = report_mod.read_parts(v5, v4)
        side = report_mod.assemble(parts, metrics.METRIC_FUNCTIONS)
    saved = parts.half.observations
    published = side.v5_lines
    if not parts.half.hopless:
        return ["the fixture lost no hop rows — this check measured the complete population"]
    for name in sorted(published):
        over_saved = metrics.METRIC_FUNCTIONS[name](saved)
        line = published[name]
        if (line.hits, line.total) != (over_saved.hits, over_saved.total):
            problems.append(f"{name}: the published total is {line.hits}/{line.total}, but the "
                            f"saved population reports {over_saved.hits}/{over_saved.total} — "
                            f"the totals and the slices score different populations")
    cells = report_mod.axis_cells(saved, metrics.METRIC_FUNCTIONS, published)
    for name in sorted(cells):
        for axis, buckets in sorted(cells[name].items()):
            summed = sum(bucket.total for bucket in buckets.values())
            if summed != published[name].total:
                problems.append(f"{name}/{axis}: the buckets hold {summed} units, the "
                                f"published line {published[name].total} — the slices do not "
                                f"reconcile with the total")
    if not side.incomplete:
        problems.append("a run with a missing case's saved hops was reported as a complete "
                        "population")
    if parts.frozen.digest == complete.frozen.digest:
        problems.append("the artifact digest did not move when a case's scored hops were removed "
                        "— it does not cover the hops it scored")
    return problems


CHECKS: tuple[tuple[str, Callable[[], list[str]]], ...] = (
    ("published_lines_and_slices_score_the_saved_population",
     test_published_lines_and_slices_score_the_saved_population),
    ("real_report_prints_the_frozen_lines", test_real_report_prints_the_frozen_lines),
    ("removing_the_wiring_turns_the_check_red", test_removing_the_wiring_turns_the_check_red),
    ("the_report_does_not_destroy_the_callers_engine",
     test_the_report_does_not_destroy_the_callers_engine),
    ("poisoned_register_spelling_leaves_the_score_bytes_identical",
     test_poisoned_register_spelling_leaves_the_score_bytes_identical),
    ("production_capture_persists_a_versioned_table",
     test_production_capture_persists_a_versioned_table),
)


def main() -> int:
    failures: list[str] = []
    for name, check in CHECKS:
        try:
            problems = check()
        except Exception as error:  # noqa: BLE001 — a raised check is a red check
            problems = [f"raised {type(error).__name__}: {error}"]
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print(f"report_frozen: PASS ({len(CHECKS)} проверок)" if not failures
          else "report_frozen: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
