"""`repro <run id>`: one command, the variable NAMES, and what has moved since.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_repro

ТЗ `docs/tz-bench-harness.md` §7.3, item 22. Everything runs on files — the
registry this test writes, a run directory `test_report.build_run` wrote, a
two-line corpus snapshot and a two-line ladder — so the command that answers
«чем именно это гонялось» costs nothing to check.

Each check goes red on a revert:

  * the command names the corpus, the tier, both models and the ceiling — drop
    one and `the_command_repeats_the_run` names it;
  * the environment is NAMES — print a value and `no_value_of_the_environment_
    is_printed` finds the planted key;
  * what has moved is part of the answer — make `plan` silent about a corpus
    whose digest changed and `a_moved_corpus_is_named` goes red, along with the
    check that the command then points at the run's OWN snapshot;
  * nothing moved must be sayable — `nothing_moved_says_so` is the other side,
    without which «всё сломалось» would pass on every run.
"""
import json
import sys
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from bench.agentpii5 import contracts
from bench.agentpii5.build import RunProvenance, worktree_line
from bench.agentpii5.provider import ADMIN_TOKEN_ENV, GATEWAY_TOKEN_ENV
from bench.agentpii5.repro import UNKNOWN, ReproError, plan, render
from bench.agentpii5.report import meta_of, run_id_of
from bench.agentpii5.runinfo import RunInfoError, RunRecord, append_run, find_run, read_runs
from bench.agentpii5.test_report import RUN_ID, build_run

FAKE_KEY = "sk-ant-REPROKEY-0a1b2c3d-do-not-ship"
TREE_DIGEST = "digest-v5"
TREE_LADDER = "ladder-1"
TREE_VERSION = "0.3.16"


def _record(run_dir: Path, worktree: str) -> RunRecord:
    """One registry row, built with the REGISTRY's own dataclass and written by
    its own `append_run`: a repro that could only read a row this file spelled
    would prove nothing about the rows a run writes."""
    return RunRecord(
        run_id="6f3a91c2-0000-4000-8000-000000000001", benchmark="agentpii5",
        started="2026-09-23T10:00:00+00:00", finished="2026-09-23T10:41:00+00:00",
        state="finished", tier="medium", cases=2, repeats=3, triples_done=6,
        transport_terminated=0, model=contracts.AGENT_MODEL,
        judge_model=contracts.JUDGE_MODEL, concurrency=2, corpus_digest=TREE_DIGEST,
        ladder_digest=TREE_LADDER, label="после правки адресов", note="проверяем Б27",
        ceiling_usd=12.0, spent_usd=3.14, wall_s=2460.0, verdict="полный",
        worktree=worktree, run_dir=str(run_dir))


def _tree(root: Path, corpus_digest: str, ladder_digest: str) -> tuple[Path, Path, Path]:
    """A miniature working tree: a corpus snapshot, a ladder and a version file.

    Small on purpose — a repro command that could only be exercised against the
    real 28 MB corpus is a command nobody would exercise."""
    corpus = root / "corpus.v5.json"
    corpus.write_text(json.dumps({"corpus": [], "digest": corpus_digest}), encoding="utf-8")
    ladder = root / "ladder.json"
    ladder.write_text(json.dumps({"version": 1, "seed": 7, "corpus_sha256": ladder_digest,
                                  "tiers": {}}), encoding="utf-8")
    version = root / "version.txt"
    version.write_text(f"{TREE_VERSION}\n", encoding="utf-8")
    return corpus, ladder, version


def _registry(root: Path, rows: list[RunRecord]) -> Path:
    path = root / "runs.json"
    for row in rows:
        append_run(path, row)
    return path


def _run_with_meta(root: Path, extra: dict[str, object]) -> Path:
    """A run directory whose `meta.json` carries the provider and gateway blocks
    item 12 and item 13 add. Written over the fixture's own meta, so the rest of
    the file stays exactly what a run writes."""
    run_dir = build_run(root, RUN_ID, True)
    run_id = run_id_of(run_dir)
    meta = dict(meta_of(run_dir, run_id))
    meta.update(extra)
    (run_dir / f"{run_id}.meta.json").write_text(json.dumps(meta, ensure_ascii=False),
                                                 encoding="utf-8")
    return run_dir


def _worktree(commit: str, dirty: tuple[str, ...]) -> str:
    """The `worktree` string a RUN writes, produced BY THE WRITER.

    `build.worktree_line` is the only thing that fills that field, so the test
    spells none of its three shapes: it asks the writer for them. Restating
    «чисто …» here would let the writer's wording and the reader's expectation
    drift apart in silence — which is exactly what happened when `repro` tested
    the field for a `"commit "` prefix nothing has ever written."""
    return worktree_line(RunProvenance(
        commit=commit, branch="main", dirty=dirty, dirty_ok=bool(dirty),
        tier="medium", cases=2, corpus_cases=2, corpus_sha256=TREE_DIGEST,
        corpus_v5_sha256=TREE_DIGEST, selection_sha256="sel", ladder_corpus_sha256=TREE_DIGEST,
        ladder_tier_sha256=(), ladder_tier_names=("medium",), holdout_touched_at="",
        holdout_touched_by=""))


CLEAN_TREE = _worktree("ff426acf71af0000", ())
DIRTY_TREE = _worktree("ff426acf71af0000", (" M prototype/bench/agentpii5/metrics.py",))
UNKNOWN_TREE = _worktree("", ())


def test_the_tree_is_read_as_the_run_wrote_it() -> list[str]:
    """§6.1 IN THE REPEAT: three states of the working tree, three answers.

    The check was `worktree.startswith("commit ")` — a prefix NO writer emits —
    so every run in the registry, a clean one included, was told «числа этого
    прогона не привязаны к коммиту». A warning printed on every run is a
    warning printed on none: the reader who sees it under a run made from a
    clean tree learns to scroll past it, and the one run where it is TRUE gets
    the same line.
    """
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        corpus, ladder, version = _tree(root, TREE_DIGEST, TREE_LADDER)
        run_dir = _run_with_meta(root / "run", {"gateway": {
            "mode": "inprocess", "base_url": None, "engine_version": TREE_VERSION,
            "image_digest": None, "learned_from": None}})
        built = {tree: plan(_record(run_dir, tree), corpus, ladder, version, {})
                 for tree in (CLEAN_TREE, DIRTY_TREE, UNKNOWN_TREE)}

        clean = built[CLEAN_TREE]
        if any("дерев" in line for line in clean.moved):
            problems.append(f"a clean tree is reported as moved: {clean.moved}")
        if not any(CLEAN_TREE in line and "привязаны к этому коммиту" in line
                   for line in clean.notes):
            problems.append(f"a clean tree is not tied to its commit in the notes: "
                            f"{clean.notes}")

        dirty = built[DIRTY_TREE]
        if not any(DIRTY_TREE in line and "не привязаны к коммиту" in line
                   for line in dirty.moved):
            problems.append(f"a dirty tree is not carried into the repeat: {dirty.moved}")

        unknown = built[UNKNOWN_TREE]
        if not any(UNKNOWN in line and "к коммиту" in line for line in unknown.moved):
            problems.append(f"an unrecorded tree is not named as unknown: {unknown.moved}")
        if any("грязн" in line for line in unknown.moved):
            problems.append(f"an unrecorded tree is called dirty: {unknown.moved}")
    return problems


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_the_run_is_named_by_the_registrys_own_matcher() -> list[str]:
    """Naming a run is `runinfo.find_run`'s job and this module has no second
    matcher: «the first by name order» is exactly the rule that let two runs
    share a directory (`harness.foreign_run_ids`), and two answers to «который
    из них» would put it back."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = _record(root, CLEAN_TREE)
        second = replace(first, run_id="6f3a91c2-0000-4000-8000-000000000002")
        registry = read_runs(_registry(root, [first, second]))
        if find_run(registry, first.run_id).run_id != first.run_id:
            problems.append("an exact id did not find its row")
        try:
            find_run(registry, "6f3a91c2")
            problems.append("an ambiguous prefix picked one run")
        except RunInfoError as refused:
            if second.run_id not in str(refused):
                problems.append(f"the refusal does not list the matches: {refused}")
        try:
            find_run(registry, "нет-такого")
            problems.append("an id nobody wrote was found")
        except RunInfoError as refused:
            if "нет-такого" not in str(refused):
                problems.append(f"the refusal does not name the id: {refused}")
        if find_run(registry, second.run_id).run_id != second.run_id:
            problems.append("a unique id did not find its row")
        # A row that names no directory cannot be compared with anything, and
        # THAT refusal is this module's own.
        try:
            plan(replace(first, run_dir=""), root / "corpus.v5.json", root / "ladder.json",
                 root / "version.txt", {})
            problems.append("a registry row with no directory produced a plan")
        except ReproError as refused:
            if first.run_id not in str(refused):
                problems.append(f"the refusal does not name the run: {refused}")
    return problems


def test_the_command_repeats_the_run() -> list[str]:
    """§7.3: ONE command carrying the corpus, the tier, the seeds, the models
    with their ids and the ceiling."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        corpus, ladder, version = _tree(root, TREE_DIGEST, TREE_LADDER)
        run_dir = _run_with_meta(root / "run", {})
        registry = read_runs(_registry(root, [_record(run_dir, CLEAN_TREE)]))
        built = plan(registry[0], corpus, ladder, version, {})
        command = built.command
        for needed in ("bench.agentpii5.harness", str(corpus), "--tier", "medium",
                       "--ceiling", "12.00", "--repeats", "3", contracts.AGENT_MODEL,
                       contracts.JUDGE_MODEL, "--label"):
            if needed not in command:
                problems.append(f"the command does not carry {needed!r}: {command}")
        if command.count("python3") != 1:
            problems.append(f"it is not ONE command: {command}")
        text = "\n".join(render(built))
        for needed in ("ярус medium", "после правки адресов", "проверяем Б27", TREE_VERSION):
            if needed not in text:
                problems.append(f"the notes do not say {needed!r}")
        if "лестница" not in text or TREE_LADDER not in text:
            problems.append("the seeds (the ladder's stamp) are not printed")
    return problems


def test_no_value_of_the_environment_is_printed() -> list[str]:
    """«переменные окружения (имена, не значения)». A repro command that carried
    a key would make every terminal scrollback a credential store."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        corpus, ladder, version = _tree(root, TREE_DIGEST, TREE_LADDER)
        run_dir = _run_with_meta(root / "run", {})
        registry = read_runs(_registry(root, [_record(run_dir, CLEAN_TREE)]))
        env = {"ANTHROPIC_API_KEY": FAKE_KEY, "ANTHROPIC_AUTH_TOKEN": FAKE_KEY,
               GATEWAY_TOKEN_ENV: FAKE_KEY, ADMIN_TOKEN_ENV: FAKE_KEY}
        built = plan(registry[0], corpus, ladder, version, env)
        text = "\n".join(render(built)) + built.command
        if FAKE_KEY in text:
            problems.append("a value of an environment variable was printed")
        if "ANTHROPIC_API_KEY" not in built.environment:
            problems.append(f"the names to export are missing: {built.environment}")
        if "export ANTHROPIC_API_KEY=…" not in text:
            problems.append("the answer does not say what to export")
    return problems


def test_a_moved_corpus_is_named_and_the_command_follows_it() -> list[str]:
    """A corpus whose digest no longer matches makes the repeat a DIFFERENT run,
    so the answer says so — and points the command at the run's own snapshot,
    which `write_corpus` put there before the first dollar for exactly this."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        corpus, ladder, version = _tree(root, "digest-НОВЫЙ", "ladder-ДРУГАЯ")
        run_dir = _run_with_meta(root / "run", {})
        registry = read_runs(_registry(root, [_record(run_dir, CLEAN_TREE)]))
        built = plan(registry[0], corpus, ladder, version, {})
        moved = "\n".join(built.moved)
        if "корпус:" not in moved or TREE_DIGEST[:12] not in moved:
            problems.append(f"the moved corpus is not named: {moved}")
        if "лестница:" not in moved:
            problems.append(f"the redrawn ladder is not named: {moved}")
        if str(run_dir / "corpus.v5.json") not in built.command:
            problems.append(f"the command does not fall back to the run's own snapshot: "
                            f"{built.command}")
        # A dirty tree is its own line: §6.1 says such numbers cannot be
        # attached to a commit, and a repeat must inherit that warning.
        dirty = plan(replace(registry[0], worktree=DIRTY_TREE), corpus, ladder, version, {})
        if not any(DIRTY_TREE in one for one in dirty.moved):
            problems.append(f"a dirty tree is not carried into the repeat: {dirty.moved}")
        # An unpriced model is named with the file to edit, never silently.
        unknown = plan(replace(registry[0], model="qwen3-32b-instruct"),
                       corpus, ladder, version, {})
        if not any("PRICES" in one for one in unknown.moved):
            problems.append(f"an unpriced model is not reported: {unknown.moved}")
    return problems


def test_an_http_gateway_run_repeats_over_http() -> list[str]:
    """Item 13 travels into the repeat: a run measured against a container must
    be repeated against a container, and the two tokens it needs are named."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        corpus, ladder, version = _tree(root, TREE_DIGEST, TREE_LADDER)
        run_dir = _run_with_meta(root / "run", {"gateway": {
            "mode": "http", "base_url": "http://engine.local:8000",
            "engine_version": "0.3.18", "image_digest": "sha256:deadbeef",
            "learned_from": "GET /status"}})
        registry = read_runs(_registry(root, [_record(run_dir, CLEAN_TREE)]))
        built = plan(registry[0], corpus, ladder, version, {})
        if "--gateway http://engine.local:8000" not in built.command:
            problems.append(f"the command does not repeat over HTTP: {built.command}")
        for name in (GATEWAY_TOKEN_ENV, ADMIN_TOKEN_ENV):
            if name not in built.environment:
                problems.append(f"the repeat does not ask for {name}")
        text = "\n".join(render(built))
        if "sha256:deadbeef" not in text or "0.3.18" not in text:
            problems.append(f"the image and the version it measured are not printed: {text}")
        if not any("движок:" in one and "0.3.18" in one for one in built.moved):
            problems.append(f"a container at 0.3.18 beside a tree at {TREE_VERSION} "
                            f"is not reported as moved: {built.moved}")
    return problems


def test_nothing_moved_says_so() -> list[str]:
    """The other side of every check above: a run whose corpus, ladder, engine
    and models are all where they were must print «ничего». Without it «всё
    сломалось» would pass on every run."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        corpus, ladder, version = _tree(root, TREE_DIGEST, TREE_LADDER)
        run_dir = _run_with_meta(root / "run", {"gateway": {
            "mode": "inprocess", "base_url": None, "engine_version": TREE_VERSION,
            "image_digest": None, "learned_from": None}})
        registry = read_runs(_registry(root, [_record(run_dir, CLEAN_TREE)]))
        built = plan(registry[0], corpus, ladder, version, {})
        if built.moved:
            problems.append(f"an unchanged tree reported changes: {built.moved}")
        if "ничего: повтор — это повтор" not in "\n".join(render(built)):
            problems.append("the answer does not say that nothing moved")
    return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("the_run_is_named_by_the_registrys_own_matcher",
         test_the_run_is_named_by_the_registrys_own_matcher),
        ("the_command_repeats_the_run", test_the_command_repeats_the_run),
        ("the_tree_is_read_as_the_run_wrote_it",
         test_the_tree_is_read_as_the_run_wrote_it),
        ("no_value_of_the_environment_is_printed", test_no_value_of_the_environment_is_printed),
        ("a_moved_corpus_is_named_and_the_command_follows_it",
         test_a_moved_corpus_is_named_and_the_command_follows_it),
        ("an_http_gateway_run_repeats_over_http", test_an_http_gateway_run_repeats_over_http),
        ("nothing_moved_says_so", test_nothing_moved_says_so),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("repro: PASS" if not failures else "repro: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
