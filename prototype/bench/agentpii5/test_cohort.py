"""`cohort.py` pinned on REAL run directories, written with the real writers.

    cd prototype && PYTHONDONTWRITEBYTECODE=1 python -m bench.agentpii5.test_cohort

THE FIXTURES ARE RUN DIRECTORIES, NOT DICTS. Every test builds a directory
under `tempfile` with the same writers a live run uses — `case_v5_to_json`,
`records.arm_v5_record`, `observe`, `records.append_row` — and then reads it
through `cohort.compose_cohort`, which reaches the files through `report` and
`records` and nothing else. The single-source builders are `test_report`'s own
(`build_run`, `_drop_hops`, `_fixture_case`, `_fixture_run`, `_triple_row`), so
a change in the writer that the report's fixture would catch cannot slip past
the composer; only the multi-source builder is written here, because
`test_report` has no reason to build two directories with disjoint case ids.

EACH NEGATIVE IS THE DEFECT, NOT THE FIX. A duplicate complete row, a missing
`C2` arm, a complete triple with no hop rows, a directory that is not a run,
two directories disagreeing about one corpus case — each one is written on disk
in the shape that produced the old table, and the test demands a refusal that
NAMES it. The `uniform_experiment` test is the opposite direction on purpose:
different generation limits on the making-up runs are real (ТЗ §6.1), so they
must compose and be VISIBLE, not be refused and not be averaged into silence.
"""
import hashlib
import json
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path

from bench.agentpii4.records import ArmMeta, arm_record
from bench.agentpii5 import contracts, records
from bench.agentpii5.cohort import (
    MANIFEST_VERSION,
    CohortError,
    SourceSpec,
    cohort_to_json,
    compose_cohort,
    selection_of,
)
from bench.agentpii5.contracts import CaseV5, JudgeVerdict
from bench.agentpii5.fixtures import REAL_NAME
from bench.agentpii5.observe import observe
from bench.agentpii5.schema import case_v5_to_json
from bench.agentpii5.test_report import (
    FIXTURE_BEHAVIOURS,
    LABEL,
    NOTE,
    PROMPT_SHA,
    RUN_ID,
    STAMP,
    WORKTREE,
    _drop_hops,
    _fixture_case,
    _fixture_run,
    _triple_row,
    build_run,
)

SOURCE_A = "srcA0001"
SOURCE_B = "srcB0001"
CASES_A: tuple[tuple[str, str], ...] = (("a-0001", "single"), ("a-0002", "retry_same_tool"))
CASES_B: tuple[tuple[str, str], ...] = (("b-0001", "single"), ("b-0002", "retry_same_tool"))
PROVIDER_12000: dict[str, object] = {
    "provider": "deepseek",
    "connectors": {"max_tokens": 0, "agent_turn_limit": 12000, "judge_request_limit": 2},
}
PROVIDER_4000: dict[str, object] = {
    "provider": "deepseek",
    "connectors": {"max_tokens": 4000, "agent_turn_limit": 12000, "judge_request_limit": 2},
}


def _write_source(root: Path, run_id: str, cases: Sequence[CaseV5],
                  provider: dict[str, object] | None, ceiling_usd: float) -> Path:
    """One run directory written with the live writers. It is `test_report.
    build_run` with the case list, the provider block and the ceiling lifted
    out — the three things a multi-source fixture has to vary and the report's
    fixture has no reason to."""
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = ArmMeta("fixture", 1, 0, "sess", "success", False, None, (), "", 0.0)
    (run_dir / "corpus.json").write_text(json.dumps(
        {"corpus": [case.base.to_json() for case in cases], "digest": "digest-v4"},
        ensure_ascii=False), encoding="utf-8")
    for case in cases:
        run = _fixture_run(case)
        for arm in ("C", "I", "C2"):
            records.append_row(records.run_file(run_dir, run_id, "<run>.arms.jsonl"),
                               arm_record(replace(run.base, arm=arm), meta, case.base))
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
    records.run_file(run_dir, run_id, "<run>.spend.tsv").write_text(
        f"agent/{cases[0].base.id}/0\t{spend:.6f}\ncumulative_usd\t{spend:.6f}\n",
        encoding="utf-8")
    meta_row: dict[str, object] = {
        "run_id": run_id, "benchmark": contracts.BENCHMARK, "model": contracts.AGENT_MODEL,
        "judge_model": contracts.JUDGE_MODEL, "tier": "nano", "repeats": 1,
        "digest": f"digest-v5-{run_id}", "ceiling_usd": ceiling_usd, "spent_usd": spend,
        "label": LABEL, "note": NOTE, "worktree": WORKTREE, "prompt_sha256": PROMPT_SHA}
    if provider is not None:
        meta_row["provider"] = provider
    records.run_file(run_dir, run_id, "<run>.meta.json").write_text(
        json.dumps(meta_row, ensure_ascii=False), encoding="utf-8")
    return run_dir


def _cases(pairs: tuple[tuple[str, str], ...]) -> tuple[CaseV5, ...]:
    return tuple(_fixture_case(case_id, behaviour) for case_id, behaviour in pairs)


def _patch_triples(run_dir: Path, run_id: str,
                   mutate: Callable[[list[dict[str, object]]], None]) -> None:
    """The triples file again, after `mutate` — so the test can write a row
    shape the writer would never produce, which is the only way to pin that the
    reader refuses it."""
    path = records.run_file(run_dir, run_id, "<run>.triples.jsonl")
    rows = records.read_rows(path)
    mutate(rows)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                    encoding="utf-8")


def _drop_arm(rows: list[dict[str, object]]) -> None:
    arms = rows[0]["arms"]
    assert isinstance(arms, dict), "the fixture lost the arms table — the negative proves nothing"
    del arms["C2"]


def _refuse(rows: list[dict[str, object]]) -> None:
    rows[0]["status"] = "excluded"
    rows[0]["reason"] = "I: TimeoutError: "


def _drop_persisted_arm(run_dir: Path, run_id: str, case_id: str, arm: str) -> None:
    """One arm record deleted from `<run>.arms.jsonl` while the triples row
    still declares it. This is the negative the metadata-only check forgives."""
    path = records.run_file(run_dir, run_id, "<run>.arms.jsonl")
    rows = records.read_rows(path)
    kept = [row for row in rows
            if not (row.get("case_id") == case_id and row.get("arm") == arm)]
    assert len(kept) < len(rows), "the fixture deleted nothing — the negative proves nothing"
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in kept),
                    encoding="utf-8")


def _tamper_corpus(run_dir: Path, case_id: str, behaviour: str) -> None:
    """One shared case redefined. `behaviour` is a KNOWN field, so the typed
    round trip `report.v5_corpus` performs sees the change — patching an
    unknown key would be dropped on read and the negative would prove nothing."""
    path = run_dir / "corpus.v5.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    for row in raw["corpus"]:
        if row["base"]["id"] == case_id:
            row["behaviour"] = behaviour
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")


def _directory_sha256(run_dir: Path) -> dict[str, str]:
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(run_dir.iterdir()) if path.is_file()}


def test_no_pseudex() -> list[str]:
    bad = [name for name in sys.modules if name.split(".")[0] == contracts.FORBIDDEN_IMPORT_PREFIX]
    return [f"the engine is imported: {sorted(bad)}"] if bad else []


def test_single_source_selects_only_complete() -> list[str]:
    """The population is the complete triples and nothing else, and the ledger
    of a whole run lands under efficacy with a zero exclusion half."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = build_run(Path(tmp), RUN_ID, True)
        cohort = compose_cohort((SourceSpec(label="A", run_dir=run_dir),))
        problems: list[str] = []
        keys = tuple((one.case.base.id, one.repeat) for one in cohort.observations)
        want = tuple(sorted((case_id, 0) for case_id, _ in FIXTURE_BEHAVIOURS))
        if keys != want:
            problems.append(f"the efficacy population is not the complete set: {keys} != {want}")
        if len(cohort.sources) != 1 or len(cohort.sources[0].observations) != 2:
            problems.append("the source did not keep its own two observations")
        if cohort.exclusions:
            problems.append(f"a fully complete run produced exclusions: {cohort.exclusions}")
        source = cohort.sources[0]
        if source.spend.efficacy_usd <= 0.0 or source.spend.excluded_usd != 0.0:
            problems.append(f"the split of a whole run is wrong: {source.spend}")
        if source.spend.triples_usd != source.spend.efficacy_usd + source.spend.excluded_usd:
            problems.append("the ledger halves do not add up to the ledger")
        if cohort.version != MANIFEST_VERSION:
            problems.append(f"the manifest is not versioned: {cohort.version!r}")
        if not cohort.uniform_experiment or len(cohort.config_groups) != 1:
            problems.append("one source is not one configuration group")
        names = tuple(name for name, _ in source.input_sha256)
        if not any(name.endswith("corpus.v5.json") for name in names):
            problems.append(f"the corpus is not among the hashed inputs: {names}")
        if f"{RUN_ID}.arms.jsonl" not in names:
            problems.append(f"the persisted arms file is not among the hashed inputs: {names}")
        return problems


def test_incomplete_retry_is_excluded_but_counted() -> list[str]:
    """A key whose first attempt did not finish and whose second did: the
    complete row is the efficacy source, and the unfinished attempt stays in
    the record with its price. Dropping it is the loss the old table hid;
    counting it as an effect is the other half of the same defect."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = build_run(Path(tmp), RUN_ID, True)
        retried = _triple_row(_fixture_case(FIXTURE_BEHAVIOURS[0][0], FIXTURE_BEHAVIOURS[0][1]))
        retried["status"] = "excluded"
        retried["reason"] = "I: TimeoutError: "
        retried["cost_usd"] = 0.5
        records.append_row(records.run_file(run_dir, RUN_ID, "<run>.triples.jsonl"), retried)
        cohort = compose_cohort((SourceSpec(label="A", run_dir=run_dir),))
        source = cohort.sources[0]
        problems: list[str] = []
        if tuple((one.case.base.id, one.repeat) for one in cohort.observations) != (
                tuple(sorted((case_id, 0) for case_id, _ in FIXTURE_BEHAVIOURS))):
            problems.append("the failed retry displaced or duplicated the complete attempt")
        if len(source.excluded) != 1 or source.excluded[0].status != "excluded":
            problems.append(f"the unfinished attempt is not kept apart: {source.excluded}")
        elif source.excluded[0].cost_usd != 0.5:
            problems.append(f"the unfinished attempt lost its price: {source.excluded[0].cost_usd}")
        if source.spend.excluded_usd != 0.5:
            problems.append(f"the exclusion half of the ledger is wrong: {source.spend.excluded_usd}")
        if source.spend.efficacy_usd != 0.24:
            problems.append(f"the efficacy half of the ledger is wrong: {source.spend.efficacy_usd}")
        if source.rows != 3 or source.duplicate_attempts != 1:
            problems.append(f"the retry is not counted: rows={source.rows} "
                            f"duplicates={source.duplicate_attempts}")
        if source.retried_keys != (tuple(sorted(source.retried_keys))[0],) or len(source.retried_keys) != 1:
            problems.append(f"the retried key is not named: {source.retried_keys}")
        if source.retried_keys[0].case_id != FIXTURE_BEHAVIOURS[0][0]:
            problems.append(f"the wrong key is called retried: {source.retried_keys}")
        return problems


def test_duplicate_complete_key_is_refused() -> list[str]:
    """Two complete rows for one key in one directory is not a retry to pick
    from — it is a composition that cannot say which attempt is the effect."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = build_run(Path(tmp), RUN_ID, True)
        case = _fixture_case(FIXTURE_BEHAVIOURS[0][0], FIXTURE_BEHAVIOURS[0][1])
        records.append_row(records.run_file(run_dir, RUN_ID, "<run>.triples.jsonl"),
                           _triple_row(case))
        try:
            compose_cohort((SourceSpec(label="A", run_dir=run_dir),))
        except CohortError as error:
            text = str(error)
            return [] if (FIXTURE_BEHAVIOURS[0][0] in text and "duplicate" in text) \
                else [f"the refusal does not name the duplicate: {text}"]
        return ["two complete rows for one key were composed as one attempt"]


def test_duplicate_complete_key_across_sources_is_refused() -> list[str]:
    """The old table's own `assert` — one key owned by two directories. A set
    intersection reported it, but only for the keys that happened to coincide;
    it is a first-class refusal here."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = _write_source(root, SOURCE_A, _cases((CASES_A[0],)), PROVIDER_12000, 3.0)
        second = _write_source(root, SOURCE_B, _cases((CASES_A[0],)), PROVIDER_12000, 3.0)
        try:
            compose_cohort((SourceSpec(label="A", run_dir=first),
                            SourceSpec(label="B", run_dir=second)))
        except CohortError as error:
            text = str(error)
            return [] if (CASES_A[0][0] in text and "duplicate" in text) \
                else [f"the refusal does not name the shared key: {text}"]
        return ["one complete key was claimed by two run directories"]


def test_missing_arm_is_refused() -> list[str]:
    """A triple marked `complete` with no `C2` arm. The old sum read the status
    and never the arms map, so an arm that never ran was summed like a whole
    triple."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = build_run(Path(tmp), RUN_ID, True)
        _patch_triples(run_dir, RUN_ID, _drop_arm)
        try:
            compose_cohort((SourceSpec(label="A", run_dir=run_dir),))
        except CohortError as error:
            return [] if "C2" in str(error) else [f"the refusal does not name the arm: {error}"]
        return ["a complete triple with a missing arm was composed as whole"]


def test_missing_persisted_arm_is_refused() -> list[str]:
    """The triples row still says `C2` finished and `<run>.arms.jsonl` has no
    C2 record for the key: a control arm that never persisted is not an arm that
    ran. `<run>.arms.v5.jsonl` holds the I arm only, so the row alone could
    never prove C or C2 — the file is the evidence."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = build_run(Path(tmp), RUN_ID, True)
        case_id = FIXTURE_BEHAVIOURS[0][0]
        _drop_persisted_arm(run_dir, RUN_ID, case_id, "C2")
        rows = records.read_rows(records.run_file(run_dir, RUN_ID, "<run>.triples.jsonl"))
        declared = next(row["arms"] for row in rows if row["case_id"] == case_id)
        problems: list[str] = []
        if not isinstance(declared, dict) or "C2" not in declared:
            problems.append("the fixture lost the declared C2 arm — the negative proves nothing")
        try:
            compose_cohort((SourceSpec(label="A", run_dir=run_dir),))
        except CohortError as error:
            if "C2" not in str(error):
                problems.append(f"the refusal does not name the arm: {error}")
        else:
            problems.append("a complete triple with no persisted C2 record was composed as whole")
        return problems


def test_missing_hop_record_is_refused() -> list[str]:
    """The arms wrote, the triple says complete, and `<run>.hops.jsonl` has no
    row for the key — a run that died between the two writes. That key has no
    observation to measure, so it cannot be an effect."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = build_run(Path(tmp), RUN_ID, True)
        _drop_hops(run_dir, FIXTURE_BEHAVIOURS[1][0])
        try:
            compose_cohort((SourceSpec(label="A", run_dir=run_dir),))
        except CohortError as error:
            text = str(error)
            return [] if FIXTURE_BEHAVIOURS[1][0] in text else \
                [f"the refusal does not name the key: {text}"]
        return ["a complete triple with no hop record was composed as measured"]


def test_invalid_source_is_refused() -> list[str]:
    """A directory that is not a run — no `<run>.arms.jsonl` to name its run id,
    or nothing on disk at all. Both are refused before any field is read."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        empty = root / "empty"
        empty.mkdir()
        for run_dir in (empty, root / "does-not-exist"):
            try:
                compose_cohort((SourceSpec(label="X", run_dir=run_dir),))
            except CohortError:
                continue
            return [f"a directory that is not a run was composed: {run_dir}"]
        return []


def test_shared_corpus_case_definition_conflict_is_refused() -> list[str]:
    """Two directories that ran the same case id under different definitions.
    They cannot be added into one population: one of them measured something
    else. The row is only in one source's efficacy — the other's attempt did not
    finish — so the duplicate-key check cannot be what catches it."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = _write_source(root, SOURCE_A, _cases((CASES_A[0],)), PROVIDER_12000, 3.0)
        second = _write_source(root, SOURCE_B, _cases((CASES_A[0],)), PROVIDER_12000, 3.0)
        _patch_triples(second, SOURCE_B, _refuse)
        _tamper_corpus(second, CASES_A[0][0], "tampered")
        try:
            compose_cohort((SourceSpec(label="A", run_dir=first),
                            SourceSpec(label="B", run_dir=second)))
        except CohortError as error:
            return [] if CASES_A[0][0] in str(error) else \
                [f"the refusal does not name the case: {error}"]
        return ["two definitions of one corpus case were composed into one cohort"]


def test_two_sources_compose_with_explicit_selection() -> list[str]:
    """The positive half of the composition: two directories with disjoint keys
    make one population, and every key can be traced back to the directory it
    came from."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = _write_source(root, SOURCE_A, _cases(CASES_A), PROVIDER_12000, 3.0)
        second = _write_source(root, SOURCE_B, _cases(CASES_B), PROVIDER_4000, 8.0)
        cohort = compose_cohort((SourceSpec(label="B", run_dir=second),
                                 SourceSpec(label="A", run_dir=first)))
        problems: list[str] = []
        keys = tuple((one.case.base.id, one.repeat) for one in cohort.observations)
        want = tuple(sorted((case_id, 0) for case_id, _ in CASES_A + CASES_B))
        if keys != want:
            problems.append(f"the union is not the four complete keys: {keys}")
        if tuple(source.label for source in cohort.sources) != ("A", "B"):
            problems.append("the sources are not ordered by label, so the composition is not "
                            f"deterministic: {[source.label for source in cohort.sources]}")
        owner = {key.case_id: label for key, label in selection_of(cohort)}
        if owner != {"a-0001": "A", "a-0002": "A", "b-0001": "B", "b-0002": "B"}:
            problems.append(f"the selection is not the source of each key: {owner}")
        if any(one.ic is not None or one.cc is not None for one in cohort.observations):
            problems.append("the composition invented paired verdicts it did not read")
        return problems


def test_different_configs_are_visible_not_merged() -> list[str]:
    """The quarter really did run under different generation limits on the
    making-up runs (ТЗ §6.1). A composition that called that one uniform
    experiment would hide the difference; a composition that refused it would
    refuse the real cohort. It does neither: it groups and prints."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = _write_source(root, SOURCE_A, _cases(CASES_A), PROVIDER_12000, 3.0)
        second = _write_source(root, SOURCE_B, _cases(CASES_B), PROVIDER_4000, 8.0)
        cohort = compose_cohort((SourceSpec(label="A", run_dir=first),
                                 SourceSpec(label="B", run_dir=second)))
        problems: list[str] = []
        if cohort.uniform_experiment:
            problems.append("two different configurations were called one experiment")
        if len(cohort.config_groups) != 2:
            problems.append(f"the configurations are not grouped: {len(cohort.config_groups)}")
        by_label = {group.labels: group for group in cohort.config_groups}
        if set(by_label) != {("A",), ("B",)}:
            problems.append(f"the groups do not name their sources: {sorted(by_label)}")
        else:
            limits_b = dict(by_label[("B",)].configuration.limits)
            limits_a = dict(by_label[("A",)].configuration.limits)
            if limits_b.get("max_tokens") != "4000" or limits_a.get("max_tokens") != "0":
                problems.append(f"the changed generation limit is not visible: {limits_b}")
            if by_label[("A",)].configuration.ceiling_usd == by_label[("B",)].configuration.ceiling_usd:
                problems.append("the two ceilings read as one")
            if by_label[("A",)].fingerprint == by_label[("B",)].fingerprint:
                problems.append("two configurations fingerprint to one")
        return problems


def test_manifest_hashes_follow_the_inputs() -> list[str]:
    """The manifest is pinned to the bytes it read: the recorded digest equals
    the file's, composing twice is stable, and a changed input moves the
    cohort's fingerprint."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = build_run(Path(tmp), RUN_ID, True)
        first = compose_cohort((SourceSpec(label="A", run_dir=run_dir),))
        problems: list[str] = []
        corpus = run_dir / "corpus.v5.json"
        recorded = {name: digest for name, digest in first.sources[0].input_sha256}
        actual = hashlib.sha256(corpus.read_bytes()).hexdigest()
        if recorded.get("corpus.v5.json") != actual:
            problems.append("the recorded corpus hash is not the file's hash")
        if first.fingerprint != compose_cohort(
                (SourceSpec(label="A", run_dir=run_dir),)).fingerprint:
            problems.append("two compositions of one directory disagree")
        corpus.write_text(corpus.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        second = compose_cohort((SourceSpec(label="A", run_dir=run_dir),))
        if second.sources[0].input_sha256 == first.sources[0].input_sha256:
            problems.append("a changed input file did not change the recorded hashes")
        if second.fingerprint == first.fingerprint:
            problems.append("a changed input file did not move the cohort fingerprint")
        return problems


def test_sources_are_not_modified() -> list[str]:
    """Composition reads. Not one byte of a run directory may move — the runs
    are the only copy of what happened."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = _write_source(root, SOURCE_A, _cases(CASES_A), PROVIDER_12000, 3.0)
        second = _write_source(root, SOURCE_B, _cases(CASES_B), PROVIDER_4000, 8.0)
        before = (_directory_sha256(first), _directory_sha256(second))
        compose_cohort((SourceSpec(label="A", run_dir=first),
                        SourceSpec(label="B", run_dir=second)))
        after = (_directory_sha256(first), _directory_sha256(second))
        return ["the composition rewrote a source directory"] if before != after else []


def test_manifest_is_versioned_and_carries_no_corpus_value() -> list[str]:
    """The manifest is the record a later reader pins: it names its own version,
    its own fingerprint, which source owns which key — and not one value from
    the corpus, because a manifest is a file that gets copied around."""
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = build_run(Path(tmp), RUN_ID, True)
        cohort = compose_cohort((SourceSpec(label="A", run_dir=run_dir),))
        manifest = cohort_to_json(cohort)
        problems: list[str] = []
        if manifest.get("version") != MANIFEST_VERSION:
            problems.append(f"the manifest carries no version: {manifest.get('version')!r}")
        if manifest.get("fingerprint") != cohort.fingerprint:
            problems.append("the manifest fingerprint is not the cohort's")
        selection = manifest.get("selection")
        if not isinstance(selection, list) or len(selection) != 2:
            problems.append(f"the manifest does not name the selection: {selection!r}")
        elif not all(isinstance(row, dict) and row.get("source") == "A" for row in selection):
            problems.append("the selection rows lost their source")
        if REAL_NAME in json.dumps(manifest, ensure_ascii=False):
            problems.append("a corpus value reached the manifest")
        if manifest.get("uniform_experiment") is not True:
            problems.append("one configuration is not reported as uniform")
        return problems


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("no_pseudex", test_no_pseudex),
        ("single_source_selects_only_complete", test_single_source_selects_only_complete),
        ("incomplete_retry_is_excluded_but_counted", test_incomplete_retry_is_excluded_but_counted),
        ("duplicate_complete_key_is_refused", test_duplicate_complete_key_is_refused),
        ("duplicate_complete_key_across_sources_is_refused",
         test_duplicate_complete_key_across_sources_is_refused),
        ("missing_arm_is_refused", test_missing_arm_is_refused),
        ("missing_persisted_arm_is_refused", test_missing_persisted_arm_is_refused),
        ("missing_hop_record_is_refused", test_missing_hop_record_is_refused),
        ("invalid_source_is_refused", test_invalid_source_is_refused),
        ("shared_corpus_case_definition_conflict_is_refused",
         test_shared_corpus_case_definition_conflict_is_refused),
        ("two_sources_compose_with_explicit_selection",
         test_two_sources_compose_with_explicit_selection),
        ("different_configs_are_visible_not_merged",
         test_different_configs_are_visible_not_merged),
        ("manifest_hashes_follow_the_inputs", test_manifest_hashes_follow_the_inputs),
        ("sources_are_not_modified", test_sources_are_not_modified),
        ("manifest_is_versioned_and_carries_no_corpus_value",
         test_manifest_is_versioned_and_carries_no_corpus_value),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("cohort: PASS" if not failures else "cohort: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
