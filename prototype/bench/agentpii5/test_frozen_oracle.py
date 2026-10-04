"""M04 — the scoring oracle is FROZEN: no mutable engine can move a saved number.

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.test_frozen_oracle          # ~4 s

WHAT M04 FOUND. `bench/agentpii5` scores saved artifacts with its own records
and arithmetic, but the WIDER oracle it belongs to still reaches the engine
LAZILY: v4's taxonomy calls v3 `classify_break`, whose `_street_repaired`
imports `pseudex.address.register_spelling` inside the function. A benchmark
whose oracle asks the thing under test whether it was right can be moved by
editing the engine — and then «the engine improved» and «the scorer changed its
mind» are one number. `frozen_oracle.py` is the answer: the repair verdict is
FROZEN DATA captured from one engine, never a live call at scoring time, and
the scoring path runs behind a firewall that refuses to import `pseudex` at all.

WHAT THIS FILE HOLDS, in one line each:

  * the oracle IMPORTS with `pseudex` (and `pseudex.address`/`pseudex.detect_all`
    in particular) blocked — the acceptance sentence of the M04 row;
  * identical saved artifacts score IDENTICALLY with the engine monkeypatched to
    raise, removed from `sys.modules`, or absent altogether;
  * `repair_verdict` answers from the frozen witness and NEVER imports the
    engine, and says `None` — not `False` — when it holds no witness, because a
    missing answer is not «not repaired»;
  * the frozen digest is content-addressed, so a moved artifact moves it — and
    it names the CORPUS CONTENT, the SCORED HOPS and the WITNESS TABLE as well
    as the rows, so a corpus edited in place under the same ids, a smaller
    scored population or another frozen verdict moves it too;
  * `artifact_digest` demands an EXPLICIT population: the defaults that let a
    caller mint a second, differently-scoped address under one oracle version
    are gone, and the ambiguous call is a `TypeError`;
  * the scorer carries no corpus literal: no case id, no PII value is written
    into `frozen_oracle.py`, so it cannot special-case a fixture.
"""
from __future__ import annotations

import dataclasses
import importlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator

from bench.agentpii4 import schema as v4schema
from bench.agentpii4.records import ArmMeta
from bench.agentpii5 import contracts, frozen_oracle, observe, perfect, records
from bench.agentpii5.contracts import CaseV5, Line
from bench.agentpii5.schema import case_v5_to_json


# --- the sample every check runs on --------------------------------------------------

def _meta() -> ArmMeta:
    return ArmMeta(model="frozen-oracle-test", turns=1, duration_ms=0, session_id="",
                   subtype="", is_error=False, api_error_status=None, errors=(),
                   reason="", cap_usd=0.0)


def _sample(limit: int = 12) -> tuple[list[object], list[dict[str, object]]]:
    """(cases, saved rows) — a RIGHT gateway's artifacts, written the way a run
    writes them, so every check scores a file and not a live object."""
    cases = perfect.cases_of_tier(perfect.load_cases(perfect.CORPUS_PATH),
                                  perfect.load_ladder(perfect.LADDER_PATH), "nano")[:limit]
    rows = [records.arm_v5_record(perfect.simulate(case), _meta(), case.base)
            for case in cases]
    return list(cases), rows


# --- the checks ----------------------------------------------------------------------

def test_imports_with_engine_blocked() -> list[str]:
    """The acceptance sentence: importing the oracle with the engine's detector
    and address modules blocked SUCCEEDS. A module that cannot be imported
    without the thing it scores is not an independent oracle."""
    problems: list[str] = []
    with frozen_oracle.forbid_engine():
        for name in list(sys.modules):
            if name.startswith("bench.agentpii5.frozen_oracle"):
                del sys.modules[name]
        try:
            module = importlib.import_module("bench.agentpii5.frozen_oracle")
        except Exception as error:  # noqa: BLE001 — the failure IS the finding
            return [f"importing frozen_oracle with the engine blocked raised "
                    f"{type(error).__name__}: {error}"]
        if not hasattr(module, "score_artifacts"):
            problems.append("frozen_oracle imported but carries no `score_artifacts`")
    left = frozen_oracle.engine_modules_loaded()
    if left:
        problems.append(f"the engine leaked into the oracle: {sorted(left)}")
    return problems


def test_engine_firewall_can_go_red() -> list[str]:
    """AN INSTRUMENT THAT CANNOT FAIL IS NOT AN INSTRUMENT: the firewall must
    refuse a loaded `pseudex` module, or it certifies nothing."""
    problems: list[str] = []
    python = "псевдо"
    sys.modules["pseudex"] = type(sys)(python)  # type: ignore[assignment]
    try:
        frozen_oracle.assert_engine_free()
        problems.append("assert_engine_free accepted a loaded `pseudex` module")
    except frozen_oracle.EngineDependencyError:
        pass
    finally:
        del sys.modules["pseudex"]
    if not frozen_oracle.EngineDependencyError:
        problems.append("no EngineDependencyError exists")
    try:
        with frozen_oracle.forbid_engine():
            importlib.import_module("pseudex.address")
        problems.append("forbid_engine allowed `pseudex.address` to be imported")
    except frozen_oracle.EngineDependencyError:
        pass
    except ImportError as error:
        problems.append(f"forbid_engine raised {type(error).__name__}, not "
                        f"EngineDependencyError: {error}")
    return problems


def test_identical_artifacts_score_identically_without_engine() -> list[str]:
    """THE M04 SENTENCE. The same bytes score the same number when the engine is
    monkeypatched to raise and when it is gone — because scoring never asks it."""
    cases, rows = _sample()
    first = frozen_oracle.score_artifacts(cases, rows)

    class Poison:
        def __getattr__(self, name: str) -> object:
            raise AssertionError(f"the oracle reached the engine: pseudex.{name}")

    saved = {name: sys.modules[name] for name in list(sys.modules)
             if name.split(".")[0] == "pseudex"}
    for name in saved:
        del sys.modules[name]
    sys.modules["pseudex"] = Poison()  # type: ignore[assignment]
    sys.modules["pseudex.address"] = Poison()  # type: ignore[assignment]
    sys.modules["pseudex.detect_all"] = Poison()  # type: ignore[assignment]
    try:
        second = frozen_oracle.score_artifacts(cases, rows)
    finally:
        for name in ("pseudex", "pseudex.address", "pseudex.detect_all"):
            sys.modules.pop(name, None)
        sys.modules.update(saved)

    problems: list[str] = []
    for name in sorted(set(first.lines) | set(second.lines)):
        one, two = first.lines.get(name), second.lines.get(name)
        if one != two:
            problems.append(f"{name}: {one} with the engine, {two} without it")
    if first.digest != second.digest:
        problems.append(f"the artifact digest moved: {first.digest} → {second.digest}")
    return problems


def test_repair_verdict_is_frozen_data_not_a_call() -> list[str]:
    """`repair_verdict` reads a WITNESS; with none it says `None` (unmeasured),
    never `False`, and it never imports the engine to find out."""
    problems: list[str] = []
    witness = frozen_oracle.RepairWitness(expected="мончгорская", restored="мончегорская",
                                          repaired=True)
    table = frozen_oracle.RepairTable(witnesses=(witness,))
    got = frozen_oracle.repair_verdict("мончгорская", "мончегорская", table)
    if got is not True:
        problems.append(f"a witnessed repair came back {got!r}, not True")
    unknown = frozen_oracle.repair_verdict("вишнёвая", "вишневая", table)
    if unknown is not None:
        problems.append(f"an unwitnessed pair came back {unknown!r}, not None — "
                        f"«no witness» is not «not repaired»")
    with frozen_oracle.forbid_engine():
        frozen_oracle.repair_verdict("мончгорская", "мончегорская", table)
        frozen_oracle.repair_verdict("иная", "другая", table)
    left = frozen_oracle.engine_modules_loaded()
    if left:
        problems.append(f"repair_verdict imported the engine: {sorted(left)}")
    return problems


def test_frozen_table_round_trips_through_json() -> list[str]:
    """The witness is DATA, so it survives the file the run was saved to."""
    problems: list[str] = []
    table = frozen_oracle.RepairTable(witnesses=(
        frozen_oracle.RepairWitness("мончгорская", "мончегорская", True),
        frozen_oracle.RepairWitness("лениа", "ленина", True),
        frozen_oracle.RepairWitness("садовая", "садовая", False),
    ))
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "repairs.json"
        table.write(path)
        again = frozen_oracle.RepairTable.read(path)
    if again != table:
        problems.append(f"the table did not round-trip: {again!r} != {table!r}")
    if frozen_oracle.repair_verdict("мончгорская", "мончегорская", again) is not True:
        problems.append("the reloaded table lost its witness")
    return problems


def test_digest_is_content_addressed() -> list[str]:
    """A moved artifact must move the digest — otherwise «identical artifacts
    score identically» is satisfied by a digest that reads nothing."""
    cases, rows = _sample(limit=4)
    first = frozen_oracle.score_artifacts(cases, rows).digest
    moved = [dict(row) for row in rows]
    moved[0] = {**moved[0], "reply": str(moved[0].get("reply", "")) + "!"}
    second = frozen_oracle.score_artifacts(cases, moved).digest
    same = frozen_oracle.score_artifacts(cases, [dict(row) for row in rows]).digest
    problems: list[str] = []
    if first != same:
        problems.append("two reads of the same rows produced two digests")
    if first == second:
        problems.append("a changed artifact left the digest alone")
    return problems


def test_digest_covers_the_scored_hops_and_the_witness() -> list[str]:
    """OBS: the digest names the POPULATION the lines were scored over and the
    witness table they were judged against — not only the corpus ids and rows.

    A digest over `(cases, rows)` was blind to two things that decide a saved
    number. Remove one case's hops and the same rows score a smaller population
    (the report does exactly that on a hole) while the address sat still; judge
    the same hops against another `RepairTable` and a repair verdict can flip
    while the address sat still. Both are measured here, and the same inputs
    twice must still give one digest."""
    cases, rows = _sample()
    observations = tuple(observe.observe(case, perfect.simulate(case), None, None) for case in cases)
    problems: list[str] = []
    if not observations or not any(one.hops for one in observations):
        return ["the sample produced no hops — the digest check measured nothing"]
    base = frozen_oracle.score_observations(observations, cases, rows)
    again = frozen_oracle.score_observations(observations, cases, rows)
    if base.digest != again.digest:
        problems.append("two scorings of the same population produced two digests")
    fewer = frozen_oracle.score_observations(observations[:-1], cases, rows)
    if base.digest == fewer.digest:
        problems.append("the digest ignored the scored hops: one case's hops removed, the address "
                        "unchanged — the digest does not name the population it scored")
    pairs = frozen_oracle.repair_pairs(observations)
    if not pairs:
        problems.append("the sample produced no LOC pair — the witness half of this check "
                        "measured nothing")
    else:
        table = frozen_oracle.freeze_repairs(pairs, lambda word: word)
        witnessed = frozen_oracle.score_observations(observations, cases, rows, table)
        if witnessed.lines != base.lines:
            problems.append("the frozen witness moved a LINE; it may only move the digest and "
                            "the measured/unmeasured counts")
        if base.digest == witnessed.digest:
            problems.append("the digest ignored the repair witness the same hops were judged "
                            "against")
    return problems


def _same_id_mutations(case: CaseV5) -> list[tuple[str, CaseV5]]:
    """FOUR content edits of ONE case, each of a field a printed line or an axis
    reads, and NOT ONE id moved.

    `dataclasses.replace` on the frozen cases keeps the case id, the PII item id
    and every hop reference byte-identical, so a digest that stays put across
    these is a digest that names the id list and not the population the lines
    were scored over. The four fields are exactly the ones the review's
    counterexample moved: `negatives` (`overmask` counts them), a PII item's own
    `value`/`canonical` (`consistency`/`stability` compare them), `register`
    (the axis buckets slice by it) and a scripted message (the axes count it)."""
    base = case.base
    other_register = next(one for one in v4schema.REGISTERS if one != base.register)
    item = base.pii[0]
    message = base.messages[1]
    return [
        ("negatives", dataclasses.replace(case, base=dataclasses.replace(
            base, negatives=base.negatives + (base.negatives[0],)))),
        ("pii value", dataclasses.replace(case, base=dataclasses.replace(
            base, pii=(dataclasses.replace(item, value=item.value + "X",
                                           canonical=item.canonical + "X"),) + base.pii[1:]))),
        ("register", dataclasses.replace(case, base=dataclasses.replace(
            base, register=other_register))),
        ("messages", dataclasses.replace(case, base=dataclasses.replace(
            base, messages=(base.messages[0],
                            dataclasses.replace(message,
                                                content=message.content + "!"))))),
    ]


def test_digest_moves_when_corpus_content_moves_under_the_same_ids() -> list[str]:
    """F1: the corpus CONTENT is in the address, not only its id list.

    `artifact_digest` used to fold the corpus down to `sorted(case.base.id …)`.
    The lines are scored against the case OBJECTS — `overmask` counts
    `negatives`, `consistency`/`stability` enumerate `pii`, the axes read
    `register` and `messages` — so a corpus edited in place under the same ids
    moved a printed total while the digest sat still: two measurements, one
    versioned address. Each of the four id-preserving edits below must move it.
    """
    cases, rows = _sample()
    problems: list[str] = []
    first = cases[0]
    if not first.base.negatives or len(first.base.messages) < 2 or not first.base.pii:
        return ["the sample carries no negative / second message / PII item — "
                "this check measured nothing"]
    ids = sorted(case.base.id for case in cases)
    base = frozen_oracle.score_artifacts(cases, rows)
    mutations = _same_id_mutations(first)
    for label, mutated in mutations:
        corpus = [mutated] + list(cases[1:])
        moved_ids = sorted(case.base.id for case in corpus)
        if moved_ids != ids:
            problems.append(f"{label}: the mutation moved an id — it must keep them: {moved_ids}")
            continue
        score = frozen_oracle.score_artifacts(corpus, rows)
        if score.digest == base.digest:
            problems.append(
                f"{label}: the corpus content changed under the same ids and the digest did not "
                f"move ({base.digest[:12]}) — the address names the ids, not the population the "
                f"lines were scored over")
    # AND THE HAZARD WAS REAL: at least one of these edits moves a PRINTED line,
    # so an unmoved digest is two measurements under one address, not a no-op.
    negatives = next(one for label, one in mutations if label == "negatives")
    moved = frozen_oracle.score_artifacts([negatives] + list(cases[1:]), rows)
    if moved.lines == base.lines:
        problems.append("no same-id edit in this sample moves a printed line, so the digest check "
                        "above proves nothing about the F1 hazard")
    return problems


def test_digest_is_corpus_order_and_process_stable() -> list[str]:
    """DETERMINISTIC ORDER: the address is a function of the bytes, not of the
    caller's list order and not of the process's hash seed.

    The corpus half is ordered by each case's own canonical form, so handing the
    same cases in another order is the same population. The subprocess half is
    the instrument for the other failure: a `set`/`frozenset` reaching the blob
    serialises in hash order, so two processes with two `PYTHONHASHSEED`s would
    mint two addresses for one population — and no single-process check can see
    it."""
    cases, rows = _sample(limit=4)
    problems: list[str] = []
    forward = frozen_oracle.score_artifacts(cases, rows).digest
    backward = frozen_oracle.score_artifacts(list(reversed(cases)), rows).digest
    if forward != backward:
        problems.append(f"reversing the corpus moved the digest: {forward[:12]} → {backward[:12]}")
    prototype = pathlib.Path(frozen_oracle.__file__).resolve().parents[2]
    script = (
        "from bench.agentpii4.records import ArmMeta\n"
        "from bench.agentpii5 import frozen_oracle, perfect, records\n"
        "cases = list(perfect.cases_of_tier(perfect.load_cases(perfect.CORPUS_PATH),"
        " perfect.load_ladder(perfect.LADDER_PATH), 'nano'))[:4]\n"
        "meta = ArmMeta(model='frozen-oracle-test', turns=1, duration_ms=0, session_id='',"
        " subtype='', is_error=False, api_error_status=None, errors=(), reason='', cap_usd=0.0)\n"
        "rows = [records.arm_v5_record(perfect.simulate(case), meta, case.base)"
        " for case in cases]\n"
        "print(frozen_oracle.score_artifacts(cases, rows).digest)\n")
    seen: dict[str, str] = {}
    for seed in ("0", "1"):
        run = subprocess.run([sys.executable, "-c", script], cwd=str(prototype),
                             env={**os.environ, "PYTHONPATH": str(prototype),
                                  "PYTHONHASHSEED": seed},
                             capture_output=True, text=True)
        if run.returncode != 0:
            problems.append(f"the PYTHONHASHSEED={seed} reread failed: "
                            f"{run.stderr.strip()[-300:]}")
            continue
        seen[seed] = run.stdout.strip().splitlines()[-1]
    if len(set(seen.values())) > 1:
        problems.append(f"two hash seeds produced two addresses for one population: {seen}")
    if seen and forward not in seen.values():
        problems.append(f"the reread address is not the in-process one: {seen} vs {forward[:12]}")
    return problems


def test_artifact_digest_demands_an_explicit_population() -> list[str]:
    """F2: ONE ORACLE VERSION MUST NOT CARRY TWO POPULATIONS BY DEFAULT.

    `artifact_digest(cases, rows)` used to fill in `observations=()` and
    `repairs=None`, so an artifact-only caller minted a SECOND address under the
    same `FROZEN_ORACLE_VERSION` as the scored path — a digest quoted out of
    context could not be told from the population-scored one. The population is
    a required argument now: the ambiguous call is a `TypeError`, and a caller
    that scored no hops has to SAY so."""
    cases, rows = _sample(limit=4)
    problems: list[str] = []
    try:
        frozen_oracle.artifact_digest(cases, rows)  # type: ignore[call-arg]
    except TypeError:
        pass
    else:
        problems.append("artifact_digest(cases, rows) still invents a population from defaults — "
                        "two addresses under one oracle version")
    observations = tuple(observe.observe(case, perfect.simulate(case), None, None) for case in cases)
    if not any(one.hops for one in observations):
        problems.append("the sample produced no hops — this check measured nothing")
        return problems
    scored = frozen_oracle.score_observations(observations, cases, rows)
    explicit_empty = frozen_oracle.artifact_digest(cases, rows, (), None)
    if explicit_empty == scored.digest:
        problems.append("an explicitly hop-free population produced the scored address — the "
                        "digest does not name the population at all")
    return problems


def test_no_corpus_literal_in_the_scorer() -> list[str]:
    """NO FIXTURE LITERALS SPECIAL-CASED IN THE SCORER: not one PII value the
    corpus carries, and not one case id, appears in the oracle's source."""
    problems: list[str] = []
    source = pathlib.Path(frozen_oracle.__file__).read_text(encoding="utf-8")
    cases = perfect.load_cases(perfect.CORPUS_PATH)
    literals: set[str] = set()
    for case in cases:
        literals.add(case.base.id)
        for item in case.base.pii:
            for text in (item.value, item.canonical):
                if len(text) >= 6:
                    literals.add(text)
    found = sorted(one for one in literals if one in source)
    if found:
        problems.append(f"corpus literals written into the scorer: {found[:5]}")
    return problems


def test_score_prints_the_lines_the_report_reads() -> list[str]:
    """The frozen score must be the SAME lines `metrics` prints, so the frozen
    path is a replacement and not a second opinion."""
    cases, rows = _sample()
    score = frozen_oracle.score_artifacts(cases, rows)
    problems: list[str] = []
    for name in perfect.SINGLE_ARM_METRICS:
        if name not in score.lines:
            problems.append(f"{name}: the frozen score dropped a line the report reads")
    for name, line in score.lines.items():
        if not isinstance(line, Line):
            problems.append(f"{name}: printed {type(line).__name__}, not Line")
    return problems


def test_report_path_prints_the_frozen_lines() -> list[str]:
    """THE M04 INTEGRATION SENTENCE: the report the product PRINTS is built from
    the frozen score, not from a second call into `metrics` beside it.

    A unit test of `score_artifacts` cannot see an orphan; this one reads a real
    saved run directory and demands that every line `assemble` publishes is the
    line `read_parts` already computed behind the engine firewall."""
    import tempfile as _tempfile
    from bench.agentpii5 import report as report_mod, test_report
    problems: list[str] = []
    with _tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        v5 = test_report.build_run(root, test_report.RUN_ID, True)
        v4 = test_report.build_run(root, "baseline01", False)
        parts = report_mod.read_parts(v5, v4)
        side = report_mod.assemble(parts, report_mod.METRIC_FUNCTIONS)
    if parts.frozen.oracle_version != frozen_oracle.FROZEN_ORACLE_VERSION:
        problems.append(f"the report names oracle {parts.frozen.oracle_version!r}, not the "
                        f"current {frozen_oracle.FROZEN_ORACLE_VERSION!r}")
    if not parts.frozen.digest:
        problems.append("the report carries no artifact digest")
    shared = [name for name in side.v5_lines if name in parts.frozen.lines]
    if not shared:
        problems.append("the report printed no line the frozen scorer produced — the oracle "
                        "is an orphan again")
    for name in shared:
        if side.v5_lines[name] != parts.frozen.lines[name]:
            problems.append(f"{name}: printed {side.v5_lines[name]}, the frozen score has "
                            f"{parts.frozen.lines[name]}")
    return problems


def test_saved_run_rescores_byte_identically_under_poison() -> list[str]:
    """A SAVED RUN WITH A REPAIRED LOC PAIR, re-scored with the engine poisoned
    and unloaded, prints the same bytes.

    This is the sentence the M04 row is written about: «the gateway improved»
    and «the scorer asked the engine again» must not be one number. The run is
    written to disk first, so the second score reads the same artifacts the
    first one did and nothing is held in memory between them."""
    import tempfile as _tempfile
    from bench.agentpii5 import report as report_mod
    problems: list[str] = []
    with _tempfile.TemporaryDirectory() as tmp:
        run_dir = pathlib.Path(tmp) / "run01"
        run_dir.mkdir(parents=True)
        cases = perfect.cases_of_tier(perfect.load_cases(perfect.CORPUS_PATH),
                                      perfect.load_ladder(perfect.LADDER_PATH), "nano")
        (run_dir / "corpus.v5.json").write_text(json.dumps(
            {"corpus": [case_v5_to_json(case) for case in cases],
             "digest": "saved-run"}, ensure_ascii=False), encoding="utf-8")
        for case in cases:
            run = perfect.simulate(case)
            records.append_row(records.run_file(run_dir, "run01", "<run>.arms.v5.jsonl"),
                               records.arm_v5_record(run, _meta(), case.base))
            for hop in observe.observe(case, run, None, None).hops:
                records.append_row(records.run_file(run_dir, "run01", "<run>.hops.jsonl"),
                                   records.hop_observation_to_json(hop))
        read_cases = report_mod.v5_corpus(run_dir)
        rows = records.merged_v5_records(run_dir)
        by_id = report_mod.v5_cases(run_dir)
        pairs = frozen_oracle.repair_pairs(tuple(
            observe.observe(by_id[records.arm_v5_from_record(dict(row)).base.case_id],
                            records.arm_v5_from_record(dict(row)), None, None)
            for row in rows))
        first = frozen_oracle.score_artifacts(read_cases, rows)
        pairs_count = len(pairs)
        if not pairs_count:
            problems.append("the sample produced no LOC pair, so the repaired-street half of "
                            "this check measured nothing")

        # POISON THE ENGINE AND UNLOAD IT, then score the SAME files again.
        saved = {name: sys.modules[name] for name in list(sys.modules)
                 if name.split(".")[0] == "pseudex"}
        for name in saved:
            del sys.modules[name]
        sys.modules["pseudex"] = Poison()  # type: ignore[assignment]
        sys.modules["pseudex.address"] = Poison()  # type: ignore[assignment]
        sys.modules["pseudex.detect_all"] = Poison()  # type: ignore[assignment]
        try:
            second = frozen_oracle.score_artifacts(report_mod.v5_corpus(run_dir),
                                                   records.merged_v5_records(run_dir))
        finally:
            for name in ("pseudex", "pseudex.address", "pseudex.detect_all"):
                sys.modules.pop(name, None)
            sys.modules.update(saved)
    for name in sorted(set(first.lines) | set(second.lines)):
        if first.lines.get(name) != second.lines.get(name):
            problems.append(f"{name}: {first.lines.get(name)} with the engine, "
                            f"{second.lines.get(name)} with it poisoned")
    if first.digest != second.digest:
        problems.append(f"the digest moved under poisoning: {first.digest} → {second.digest}")
    # A run with LOC pairs and NO captured table is UNMEASURED, never clean.
    if pairs_count and first.repairs_unmeasured != pairs_count:
        problems.append(f"{pairs_count} LOC pairs but {first.repairs_unmeasured} counted "
                        f"unmeasured — an absent witness is not «not repaired»")
    # And a witness makes the same pair MEASURED without the engine.
    table = frozen_oracle.freeze_repairs(pairs, lambda word: word)
    with frozen_oracle.forbid_engine():
        witnessed = frozen_oracle.score_artifacts(read_cases, rows, table)
    if witnessed.repairs_measured + witnessed.repairs_unmeasured != pairs_count:
        problems.append("the witnessed table lost a pair")
    return problems


class Poison:
    """Any attribute read from the poisoned engine is a failure, not a value."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"the oracle reached the engine: pseudex.{name}")


CHECKS: tuple[tuple[str, Callable[[], list[str]]], ...] = (
    ("imports_with_engine_blocked", test_imports_with_engine_blocked),
    ("engine_firewall_can_go_red", test_engine_firewall_can_go_red),
    ("identical_artifacts_score_identically_without_engine",
     test_identical_artifacts_score_identically_without_engine),
    ("repair_verdict_is_frozen_data_not_a_call", test_repair_verdict_is_frozen_data_not_a_call),
    ("frozen_table_round_trips_through_json", test_frozen_table_round_trips_through_json),
    ("digest_is_content_addressed", test_digest_is_content_addressed),
    ("digest_covers_the_scored_hops_and_the_witness",
     test_digest_covers_the_scored_hops_and_the_witness),
    ("digest_moves_when_corpus_content_moves_under_the_same_ids",
     test_digest_moves_when_corpus_content_moves_under_the_same_ids),
    ("digest_is_corpus_order_and_process_stable",
     test_digest_is_corpus_order_and_process_stable),
    ("artifact_digest_demands_an_explicit_population",
     test_artifact_digest_demands_an_explicit_population),
    ("no_corpus_literal_in_the_scorer", test_no_corpus_literal_in_the_scorer),
    ("score_prints_the_lines_the_report_reads", test_score_prints_the_lines_the_report_reads),
    ("report_path_prints_the_frozen_lines", test_report_path_prints_the_frozen_lines),
    ("saved_run_rescores_byte_identically_under_poison",
     test_saved_run_rescores_byte_identically_under_poison),
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
    print(f"frozen_oracle: PASS ({len(CHECKS)} проверок, версия "
          f"{frozen_oracle.FROZEN_ORACLE_VERSION})" if not failures
          else "frozen_oracle: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
