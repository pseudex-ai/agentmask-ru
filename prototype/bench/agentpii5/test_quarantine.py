"""The case defect a run cannot tell from a product defect (пункт 21).

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_quarantine

WHAT THIS PINS THAT NOTHING ELSE DOES. `quarantine` is the only reader that
compares RUNS with each other rather than arms inside one, and its whole value
is in two negatives: a case that only the GATEWAY arm flaps on must not be
quarantined (that is the product finding the benchmark exists for), and an arm
that died of a provider error must not read as an arm that behaved differently
(that would quarantine whatever was in flight during an outage).

EVERY RUN HERE IS SYNTHETIC AND WRITTEN INTO A TEMPORARY DIRECTORY: this check
must run with no model, no network, no keys and no run of our own on disk.
"""
import ast
import json
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from bench.agentpii5 import quarantine as q
from bench.agentpii5 import runinfo

HERE: Path = Path(__file__).resolve().parent
# One conditions block, so a check that does not care about comparability does
# not have to restate it: the digest, the agent model, the judge and the tier.
CONDITIONS: dict[str, str] = {"digest": "d" * 64, "model": "agent-1",
                              "judge_model": "judge-1", "tier": "nano"}


def _arm_row(case_id: str, arm: str, repeat: int, call: str, reply: str) -> dict[str, object]:
    """A v4 arm record with the fields the fingerprint reads, and nothing else
    invented: the keys are `bench.agentpii4.records.arm_record`'s own."""
    return {"key": f"{case_id}|{arm}|{repeat}", "case_id": case_id, "arm": arm,
            "repeat": repeat, "kind": "order", "register": "chat", "cluster": "NAME:x",
            "termination": "done", "cost_usd": 0.01,
            "calls": [{"name": call, "seq": 1, "written": {"name": "Иванов"},
                       "restored": {"name": "Петров"}, "residual": {},
                       "refusal_path": "", "refusal_rule": "", "parsed": {"name": "Иванов"}}],
            "state": [], "reply": reply, "substitutes": {}, "masked_spans": {},
            "meta": {"model": "agent-1"}}


def _write_run(directory: Path, run_id: str, finished: str,
               rows: Sequence[dict[str, object]], conditions: dict[str, str]) -> Path:
    """A run directory as the harness leaves one: a meta file and arm rows."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{run_id}.meta.json").write_text(json.dumps(
        {"run_id": run_id, "benchmark": "agentpii5", "finished": finished, **conditions},
        ensure_ascii=False), encoding="utf-8")
    (directory / f"{run_id}.arms.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return directory


def _run_of(folder: Path, name: str, day: str, calls: dict[tuple[str, str], str],
            conditions: dict[str, str]) -> Path:
    """One run over a fixed cast of cases: `calls` says which tool each (case,
    arm) called, which is the whole of what the fingerprint sees here."""
    rows = [_arm_row(case_id, arm, 1, call, f"ответ {name}")
            for (case_id, arm), call in calls.items()]
    return _write_run(folder / name, name, f"2026-09-{day}T10:00:00+00:00", rows, conditions)


def _cast(flap: Sequence[str], gateway_only: str, steady: str) -> dict[tuple[str, str], str]:
    """The three cases every window check uses: one that flaps at every arm, one
    that flaps at the gateway arm alone, and one that never moves."""
    plan: dict[tuple[str, str], str] = {}
    for index, arm in enumerate(q.ARMS):
        plan[("flap", arm)] = flap[index]
        plan[("gateway-only", arm)] = gateway_only if arm == "I" else "create_order"
        plan[("steady", arm)] = steady
    return plan


def test_three_flapping_runs_are_quarantined() -> list[str]:
    """The positive and the two negatives in one window: a case whose every arm
    behaves differently from run to run is a CASE defect; a case only the
    gateway arm moves on is a PRODUCT finding and must be left alone."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        dirs = [
            _run_of(root, "run-a", "01", _cast(("t1", "t1", "t1"), "create_order", "t0"),
                    CONDITIONS),
            _run_of(root, "run-b", "02", _cast(("t2", "t2", "t2"), "update_order", "t0"),
                    CONDITIONS),
            _run_of(root, "run-c", "03", _cast(("t3", "t3", "t3"), "cancel_order", "t0"),
                    CONDITIONS)]
        readings = [q.read_run(one) for one in dirs]
        suspects = q.unstable_cases(readings, 3)
        named = [one.case_id for one in suspects]
        if named != ["flap"]:
            problems.append(f"quarantined {named}, want ['flap']")
        if suspects and suspects[0].per_arm != tuple((arm, 3) for arm in q.ARMS):
            problems.append(f"the arms' fingerprint counts are {suspects[0].per_arm}")
        if suspects and suspects[0].runs != ("run-a", "run-b", "run-c"):
            problems.append(f"the window names {suspects[0].runs}")
        if suspects and (suspects[0].kind, suspects[0].register) != ("order", "chat"):
            problems.append(f"the suspect carries no family: {suspects[0]}")
        text = "\n".join(q.report(readings, 3))
        if "карантин: 1 случаев" not in text:
            problems.append(f"the report does not print the count: {text!r}")
        if "решение человека" not in text:
            problems.append("the report does not say that marking a case is a person's call")
        # THE OUTPUT IS IDS, HASHES AND COUNTS: no value and no reply text.
        for secret in ("Иванов", "Петров", "ответ run-a"):
            if secret in text:
                problems.append(f"the report prints {secret!r}")
    return problems


def test_two_runs_cannot_accuse_a_case() -> list[str]:
    """Пункт 21 asks for THREE consecutive runs, and the reason is that two
    separate a flapping case from one coin flip by nothing. The report says the
    window could not be filled rather than printing a clean «0»."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        dirs = [_run_of(root, "run-a", "01", _cast(("t1", "t1", "t1"), "a", "t0"), CONDITIONS),
                _run_of(root, "run-b", "02", _cast(("t2", "t2", "t2"), "b", "t0"), CONDITIONS)]
        readings = [q.read_run(one) for one in dirs]
        if q.unstable_cases(readings, 3):
            problems.append("two runs were enough to quarantine a case")
        text = "\n".join(q.report(readings, 3))
        if "меньше 3, сравнивать нечего" not in text:
            problems.append(f"the report does not say the window is unfilled: {text!r}")
        # …and the same two runs DO answer when the window is two: the rule is
        # the window, not a refusal built into the comparison.
        if [one.case_id for one in q.unstable_cases(readings, 2)] != ["flap"]:
            problems.append("a window of two found nothing in two flapping runs")
        try:
            q.unstable_cases(readings, 1)
            problems.append("a window of one was accepted")
        except q.QuarantineError as error:
            if "окно 1" not in str(error):
                problems.append(f"the refusal does not name the window: {error}")
    return problems


def test_runs_under_other_conditions_are_not_one_window() -> list[str]:
    """«Разные вердикты при ОДИНАКОВЫХ условиях»: a case that behaved
    differently under another model has said nothing about itself, so a window
    never crosses a change of model, judge, tier or corpus."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        other = {**CONDITIONS, "model": "agent-2"}
        dirs = [_run_of(root, "run-a", "01", _cast(("t1", "t1", "t1"), "a", "t0"), CONDITIONS),
                _run_of(root, "run-b", "02", _cast(("t2", "t2", "t2"), "b", "t0"), CONDITIONS),
                _run_of(root, "run-c", "03", _cast(("t3", "t3", "t3"), "c", "t0"), other)]
        readings = [q.read_run(one) for one in dirs]
        if q.unstable_cases(readings, 3):
            problems.append("a window crossed a change of model")
        text = "\n".join(q.report(readings, 3))
        if "условия различались: 2 набора" not in text:
            problems.append(f"the report does not say the conditions differed: {text!r}")
        for key in q.CONDITION_KEYS:
            if key not in text:
                problems.append(f"the report does not print the condition {key}")
    return problems


def test_an_arm_that_died_is_not_an_arm_that_changed() -> list[str]:
    """An excluded termination (a provider error) is a fact about the provider.
    Reading it as a change would quarantine whatever was in flight during an
    outage — the cases with the least to answer for."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        dirs = [_run_of(root, "run-a", "01", _cast(("t1", "t1", "t1"), "a", "t0"), CONDITIONS),
                _run_of(root, "run-b", "02", _cast(("t2", "t2", "t2"), "b", "t0"), CONDITIONS),
                _run_of(root, "run-c", "03", _cast(("t3", "t3", "t3"), "c", "t0"), CONDITIONS)]
        broken = [_arm_row("flap", arm, 1, "t9", "ответ") for arm in q.ARMS]
        broken[1]["termination"] = "provider_error"
        (dirs[2] / "run-c.arms.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in broken),
            encoding="utf-8")
        readings = [q.read_run(one) for one in dirs]
        if [one.case_id for one in q.unstable_cases(readings, 3)]:
            problems.append("a case one of whose arms died was quarantined anyway")
        # …and the other two arms of that run WERE read: the run is not thrown away.
        if ("flap", "C") not in readings[2].behaviour:
            problems.append("a run with one dead arm lost its live ones")
    return problems


def test_the_fingerprint_reads_the_act_and_not_the_wording() -> list[str]:
    """Substitutes are minted per run and any model words a sentence differently
    every time; neither is a property of the case, and a fingerprint over them
    would call all 1736 cases unstable. What IS a property: the tools called,
    the leaves filled, the parse, the refusal, the termination."""
    problems: list[str] = []
    base = _arm_row("c1", "I", 1, "create_order", "Здравствуйте!")
    same_act = _arm_row("c1", "I", 2, "create_order", "Добрый день, всё готово")
    same_act["calls"][0]["written"] = {"name": "Сидоров"}       # type: ignore[index]
    same_act["calls"][0]["restored"] = {"name": "Кузнецов"}     # type: ignore[index]
    if q.behaviour_fingerprint(base) != q.behaviour_fingerprint(same_act):
        problems.append("another wording and another substitute changed the fingerprint")
    for label, mutate in (
            ("другой инструмент", lambda row: row["calls"][0].__setitem__("name", "update_order")),
            ("другой лист", lambda row: row["calls"][0].__setitem__("written", {"phone": "1"})),
            ("вызов не разобран", lambda row: row["calls"][0].__setitem__("parsed", None)),
            ("отказ по правилу", lambda row: row["calls"][0].__setitem__("refusal_rule", "R7")),
            ("другое завершение", lambda row: row.__setitem__("termination", "max_steps")),
            ("нет вызовов", lambda row: row.__setitem__("calls", [])),
            ("без ответа", lambda row: row.__setitem__("reply", "  ")),
            ("записи в состоянии", lambda row: row.__setitem__("state", [{"a": 1}]))):
        changed = json.loads(json.dumps(base))
        mutate(changed)
        if q.behaviour_fingerprint(changed) == q.behaviour_fingerprint(base):
            problems.append(f"the fingerprint does not see: {label}")
    broken = json.loads(json.dumps(base))
    del broken["termination"]
    try:
        q.behaviour_fingerprint(broken)
        problems.append("a row without a termination was fingerprinted anyway")
    except q.QuarantineError as error:
        if "termination" not in str(error):
            problems.append(f"the refusal does not name the field: {error}")
    return problems


def test_a_run_that_cannot_be_read_is_named() -> list[str]:
    """A directory silently left out would make «0 unstable cases» mean «two of
    the three runs were unreadable», and the two readings look the same."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / "empty"
        root.mkdir()
        (root / "run-x.arms.jsonl").write_text("", encoding="utf-8")
        try:
            q.read_run(root)
            problems.append("a run directory with no meta file was read as a run")
        except q.QuarantineError as error:
            if "meta" not in str(error) or "empty" not in str(error):
                problems.append(f"the refusal names neither the file nor the run: {error}")
        other = _write_run(Path(folder) / "alien", "run-y", "2026-09-01T00:00:00+00:00",
                           [{**_arm_row("c1", "I", 1, "t", "r"), "arm": "Z"}], CONDITIONS)
        try:
            q.read_run(other)
            problems.append("an arm outside the three was accepted")
        except q.QuarantineError as error:
            if "'Z'" not in str(error):
                problems.append(f"the refusal does not name the arm: {error}")
    return problems


def test_the_registry_is_read_or_refused_by_name() -> list[str]:
    """`runs.json` is another component's file (§1.2): this reader takes the
    directory out of it and refuses BY NAME when a row carries none of the keys
    it knows, rather than skipping the row and comparing fewer runs than the
    person asked for."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        _run_of(root, "run-a", "01", _cast(("t1", "t1", "t1"), "a", "t0"), CONDITIONS)
        registry = root / "runs.json"
        # `run_dir` — ИМЕННО ТО ИМЯ, КОТОРОЕ ПИШЕТ РЕЕСТР (`runinfo.RunRecord`),
        # а не одно из трёх, которые этот читатель когда-то принимал: реестр
        # приехал, и набор написаний схлопнут до того единственного, что в нём
        # есть. Проверка держит связь двух файлов, написанных врозь.
        registry.write_text(json.dumps({"runs": [{"run_id": "run-a", "run_dir": "run-a"}]}),
                            encoding="utf-8")
        found = q.run_dirs_from_registry(registry)
        if found != (root / "run-a",):
            problems.append(f"the registry's relative path resolved to {found}")
        # И ИМЯ КЛЮЧА СВЕРЕНО С ТЕМ, КТО ЕГО ПИШЕТ. Фикстура выше — это наше
        # представление о чужом файле; без этой строки переименование поля в
        # `runinfo.RunRecord` оставило бы фикстуру зелёной, а карантин —
        # отказывающим на всём, что реестр действительно пишет.
        written = set(runinfo.RunRecord.__dataclass_fields__)
        if not set(q.REGISTRY_DIR_KEYS) <= written:
            problems.append(f"карантин ищет {q.REGISTRY_DIR_KEYS}, а реестр пишет "
                            f"{sorted(written)}")
        registry.write_text(json.dumps([{"run_id": "run-a", "верно": "run-a"}]),
                            encoding="utf-8")
        try:
            q.run_dirs_from_registry(registry)
            problems.append("a row naming no directory was accepted")
        except q.QuarantineError as error:
            if not all(key in str(error) for key in q.REGISTRY_DIR_KEYS):
                problems.append(f"the refusal does not name the keys it looked for: {error}")
        try:
            q.run_dirs_from_registry(root / "no-such-registry.json")
            problems.append("a registry that does not exist was read")
        except q.QuarantineError as error:
            if "no-such-registry" not in str(error):
                problems.append(f"the refusal does not name the file: {error}")
    return problems


def _cli(argv: list[str]) -> int:
    """`quarantine.main` с подменённым `sys.argv` — как у остальных команд
    пакета, чей `main` читает аргументы сам (единое написание на пакет)."""
    saved = sys.argv
    try:
        sys.argv = ["quarantine"] + argv
        return q.main()
    finally:
        sys.argv = saved


def test_the_command_runs_on_files_alone() -> list[str]:
    """`main` end to end: three run directories in, a report out, exit 0 — and
    exit 0 WITH suspects, because a suspect is a question for a person and a
    non-zero exit is how a pipeline ends up deciding which cases leave the
    corpus."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        dirs = [_run_of(root, "run-a", "01", _cast(("t1", "t1", "t1"), "a", "t0"), CONDITIONS),
                _run_of(root, "run-b", "02", _cast(("t2", "t2", "t2"), "b", "t0"), CONDITIONS),
                _run_of(root, "run-c", "03", _cast(("t3", "t3", "t3"), "c", "t0"), CONDITIONS)]
        if _cli([str(one) for one in dirs]) != 0:
            problems.append("a run with suspects exited non-zero")
        if _cli([]) != 2:
            problems.append("an invocation naming nothing exited 0")
        registry = root / "runs.json"
        registry.write_text(json.dumps({"runs": [{"run_dir": str(one)} for one in dirs]}),
                            encoding="utf-8")
        if _cli(["--runs-file", str(registry)]) != 0:
            problems.append("the registry path did not run")
    return problems


def test_nothing_here_writes() -> list[str]:
    """§7.2: «пометка — решение человека, не автоматика». The module's own AST
    is the proof, because a tool that quarantined cases by itself would shrink
    the family whose disagreement it was reporting — and nothing else in the
    repository would notice."""
    tree = ast.parse((HERE / "quarantine.py").read_text(encoding="utf-8"))
    forbidden = ("write_text", "write_bytes", "mkdir", "unlink", "rename", "rmtree", "dump")
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", "") or getattr(node.func, "id", "")
        if name in forbidden:
            found.append(f"quarantine.py:{node.lineno} calls {name}")
        if name == "open" and len(node.args) > 1:
            found.append(f"quarantine.py:{node.lineno} opens a file with a mode")
    return found


CHECKS: tuple[Callable[[], list[str]], ...] = (
    test_three_flapping_runs_are_quarantined,
    test_two_runs_cannot_accuse_a_case,
    test_runs_under_other_conditions_are_not_one_window,
    test_an_arm_that_died_is_not_an_arm_that_changed,
    test_the_fingerprint_reads_the_act_and_not_the_wording,
    test_a_run_that_cannot_be_read_is_named,
    test_the_registry_is_read_or_refused_by_name,
    test_the_command_runs_on_files_alone,
    test_nothing_here_writes)


def main() -> int:
    failures = 0
    for check in CHECKS:
        problems = check()
        if problems:
            failures += 1
            print(f"  {check.__name__}: {problems[0]}")
            for problem in problems[1:5]:
                print(f"    {problem}")
    print(f"quarantine: {len(CHECKS)} проверок · "
          + ("PASS" if not failures else f"FAIL ({failures})"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
