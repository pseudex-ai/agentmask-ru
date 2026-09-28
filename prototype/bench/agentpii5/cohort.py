"""M0 — compose ONE completed cohort out of the v5 run directories.

For `(case_id, repeat)` the composition takes exactly one COMPLETE triple, all
three arms and the hop records, and no silent «best» attempt — replacing the
audit's `set` comprehension, which could not see a duplicate complete row, never
read the arms map, and yielded the «450» later explained in
`research/hop-format-audit/README.md` §1.2 (ТЗ §6.1).

EFFICACY is the complete triples, EXCLUSIONS keep every other row with its
status, arms, reason and price, SPEND splits each ledger in two. `version` plus
`fingerprint` plus the per-source `config`/`input_sha256` ARE the manifest.

THE ROW IS METADATA, THE FILES ARE THE EVIDENCE. `<run>.arms.v5.jsonl` holds the
I arm alone, so «C2 done» on a triples row proves nothing: C and C2 are read
from `<run>.arms.jsonl` through v4's `arm_from_record`, and that file is hashed
with the rest. Conflicts are refused; configurations are not — different
generation limits on the making-up runs are grouped and carried, so
`uniform_experiment` is False rather than a silent claim. Nothing is printed, no
metric is computed, no engine is imported.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from bench.agentpii4.records import arm_from_record
from bench.agentpii5 import records, report
from bench.agentpii5.contracts import CaseV5, RunObservation
from bench.agentpii5.schema import case_v5_to_json

# A field added, renamed or redefined below is a new number.
MANIFEST_VERSION: str = "m0-cohort-1"
# The only arm names a complete triple may carry, and v4's word for a triple
# that reached its end. Neither is a named constant in v4.
REQUIRED_ARMS: tuple[str, ...] = ("C", "C2", "I")
COMPLETE_STATUS: str = "complete"
ARM_DONE: str = "done"
# What this composition reads, and therefore hashes. Not `<run>.report.json` or
# `<run>.public.json` (derived) and not `<run>.judge.jsonl` (not the population).
INPUT_FILES: tuple[str, ...] = (
    "corpus.v5.json",
    "<run>.arms.jsonl",
    "<run>.arms.v5.jsonl",
    "<run>.hops.jsonl",
    "<run>.triples.jsonl",
    "<run>.spend.tsv",
    "<run>.meta.json",
)


class CohortError(ValueError):
    """A composition that cannot be made, refused by name."""


@dataclass(frozen=True, order=True)
class TripleKey:
    case_id: str
    repeat: int


@dataclass(frozen=True)
class SourceSpec:
    label: str
    run_dir: Path


@dataclass(frozen=True)
class ExcludedAttempt:
    """A triple row kept out of efficacy and in the record, reason verbatim."""

    source: str
    run_id: str
    key: TripleKey
    status: str
    reason: str
    arms: tuple[str, ...]
    cost_usd: float
    judge_cost_usd: float
    turn_residual: int


@dataclass(frozen=True)
class SourceSpend:
    """One directory's ledger, split. `judge_usd` is inside `triples_usd`; a None
    `ledger_delta_usd` is «no ledger written», never zero."""

    label: str
    run_id: str
    triples_usd: float
    efficacy_usd: float
    excluded_usd: float
    judge_usd: float
    ledger_usd: float | None
    ledger_delta_usd: float | None


@dataclass(frozen=True)
class CohortSpend:
    triples_usd: float
    efficacy_usd: float
    excluded_usd: float
    judge_usd: float
    ledger_usd: float | None


@dataclass(frozen=True)
class RunConfiguration:
    """What decides which experiment a directory ran. `limits` is
    `provider.connectors`, where a making-up run's generation limits differ;
    `ceiling_usd` is the string "unknown" when none was recorded."""

    model: str
    judge_model: str
    tier: str
    repeats: int
    prompt_sha256: str
    ceiling_usd: str
    provider: tuple[tuple[str, str], ...]
    limits: tuple[tuple[str, str], ...]
    gateway: tuple[tuple[str, str], ...]

    def fingerprint(self) -> str:
        return _fingerprint({
            "model": self.model, "judge_model": self.judge_model, "tier": self.tier,
            "repeats": self.repeats, "prompt_sha256": self.prompt_sha256,
            "ceiling_usd": self.ceiling_usd, "provider": self.provider,
            "limits": self.limits, "gateway": self.gateway})


@dataclass(frozen=True)
class ConfigGroup:
    """One distinct configuration and its sources; more than one group is what
    makes `Cohort.uniform_experiment` False."""

    fingerprint: str
    labels: tuple[str, ...]
    configuration: RunConfiguration


@dataclass(frozen=True)
class CorpusCase:
    """One corpus case definition, hashed over `schema.case_v5_to_json`."""

    case_id: str
    definition_sha256: str
    sources: tuple[str, ...]


@dataclass(frozen=True)
class SourceProvenance:
    """One directory: what it contributed, what it cost and what it was.
    `duplicate_attempts`/`retried_keys` are the retry count a `set` cannot see."""

    label: str
    run_dir: Path
    run_id: str
    config: RunConfiguration
    complete_keys: tuple[TripleKey, ...]
    observations: tuple[RunObservation, ...]
    excluded: tuple[ExcludedAttempt, ...]
    spend: SourceSpend
    rows: int
    duplicate_attempts: int
    retried_keys: tuple[TripleKey, ...]
    corpus_cases: int
    case_fingerprints: tuple[tuple[str, str], ...]
    corpus_v5_sha256: str
    input_sha256: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Cohort:
    """The population and its record. `fingerprint` is over the version, the
    selection and every input hash — never over the measured values, which would
    move the pin when the measurement moved."""

    version: str
    fingerprint: str
    observations: tuple[RunObservation, ...]
    sources: tuple[SourceProvenance, ...]
    exclusions: tuple[ExcludedAttempt, ...]
    config_groups: tuple[ConfigGroup, ...]
    corpus_cases: tuple[CorpusCase, ...]
    spend: CohortSpend

    @property
    def uniform_experiment(self) -> bool:
        return len(self.config_groups) == 1


@dataclass(frozen=True)
class _Attempt:
    key: TripleKey
    status: str
    reason: str
    arms: tuple[tuple[str, str], ...]
    cost_usd: float
    judge_cost_usd: float
    turn_residual: int


def _canonical(value: object) -> str:
    """Sorted keys and no whitespace, so insertion order cannot fork a hash."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_table(table: dict[str, object]) -> tuple[tuple[str, str], ...]:
    """A meta table as sorted `key -> canonical JSON` pairs, so a reader SEES the
    difference rather than trusting a hash. A nested table renders as its own
    JSON string, where flattening would collide two shapes on one key path."""
    return tuple((key, _canonical(table[key])) for key in sorted(table))


def _table_of(value: object, name: str, where: Path) -> dict[str, object]:
    """A meta table, or {} when absent; a wrong type is a refusal."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CohortError(f"{where}: {name} must be an object, found {type(value).__name__}")
    return {str(key): item for key, item in value.items()}


def _meta_text(meta: dict[str, object], key: str, where: Path) -> str:
    value = meta.get(key)
    if not isinstance(value, str):
        raise CohortError(f"{where}: meta.{key} must be a string, found "
                          f"{type(value).__name__} {value!r}")
    return value


def _meta_whole(meta: dict[str, object], key: str, where: Path) -> int:
    value = meta.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CohortError(f"{where}: meta.{key} must be an integer, found "
                          f"{type(value).__name__} {value!r}")
    return value


def _configuration(meta: dict[str, object], where: Path) -> RunConfiguration:
    """`connectors` gets its own field; leaving it in `provider` too would
    fingerprint the generation limits twice."""
    provider = _table_of(meta.get("provider"), "meta.provider", where)
    limits = _table_of(provider.get("connectors"), "meta.provider.connectors", where)
    ceiling = meta.get("ceiling_usd")
    return RunConfiguration(
        model=_meta_text(meta, "model", where),
        judge_model=_meta_text(meta, "judge_model", where),
        tier=_meta_text(meta, "tier", where),
        repeats=_meta_whole(meta, "repeats", where),
        prompt_sha256=_meta_text(meta, "prompt_sha256", where),
        ceiling_usd=("unknown" if isinstance(ceiling, bool) or not isinstance(ceiling, (int, float))
                     else _canonical(ceiling)),
        provider=_render_table({key: value for key, value in provider.items()
                                if key != "connectors"}),
        limits=_render_table(limits),
        gateway=_render_table(_table_of(meta.get("gateway"), "meta.gateway", where)))


def _arm_terminations(table: dict[str, object], where: Path) -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    for name in sorted(table):
        value = table[name]
        if not isinstance(value, dict):
            raise CohortError(f"{where}: arms.{name} must be an object, found "
                              f"{type(value).__name__}")
        termination = value.get("termination")
        if not isinstance(termination, str):
            raise CohortError(f"{where}: arms.{name}.termination must be a string, found "
                              f"{type(termination).__name__} {termination!r}")
        out.append((name, termination))
    return tuple(out)


def _attempt(row: dict[str, object], path: Path) -> _Attempt:
    """One triples row through `records`' own readers, so a missing field is
    refused by name here as everywhere else."""
    kind = "triple"
    totals = records.triple_totals_from_json(row)
    return _Attempt(
        key=TripleKey(records._text(row, "case_id", kind), records._whole(row, "repeat", kind)),
        status=records._text(row, "status", kind),
        reason=records._text(row, "reason", kind),
        arms=_arm_terminations(records._table(row, "arms", kind), path),
        cost_usd=report._triple_cost(row, path),
        judge_cost_usd=totals.judge_cost_usd,
        turn_residual=totals.turn_residual)


def _require_whole_row(attempt: _Attempt, spec: SourceSpec) -> None:
    """What the ROW claims: every required arm, only those arms, each `done`."""
    names = tuple(name for name, _ in attempt.arms)
    missing = tuple(arm for arm in REQUIRED_ARMS if arm not in names)
    extra = tuple(name for name in names if name not in REQUIRED_ARMS)
    if missing or extra:
        raise CohortError(
            f"source {spec.label!r} ({spec.run_dir}): complete triple "
            f"{attempt.key.case_id}|{attempt.key.repeat} has missing arms {missing} "
            f"and unknown arms {extra}; the row carries {names}")
    unfinished = tuple(f"{name}={termination}" for name, termination in attempt.arms
                       if termination != ARM_DONE)
    if unfinished:
        raise CohortError(
            f"source {spec.label!r} ({spec.run_dir}): complete triple "
            f"{attempt.key.case_id}|{attempt.key.repeat} has arms that did not finish: "
            f"{unfinished}")


def _persisted_arms(run_dir: Path, run_id: str) -> dict[TripleKey, tuple[tuple[str, str], ...]]:
    """The arms actually ON DISK, through v4's own `arm_from_record`.

    Two records for one `(key, arm)` are refused: that is an attempt rewritten on
    disk, and taking the last one is the silent «best» this module forbids.
    """
    path = records.run_file(run_dir, run_id, "<run>.arms.jsonl")
    rows: dict[TripleKey, list[tuple[str, str]]] = {}
    for row in records.read_rows(path):
        arm = arm_from_record(row)
        rows.setdefault(TripleKey(arm.case_id, arm.repeat), []).append((arm.arm, arm.termination))
    out: dict[TripleKey, tuple[tuple[str, str], ...]] = {}
    for key, arms in rows.items():
        names = [name for name, _ in arms]
        if len(set(names)) != len(names):
            raise CohortError(f"{path}: more than one persisted record for an arm of "
                              f"{key.case_id}|{key.repeat}: {sorted(names)}")
        out[key] = tuple(sorted(arms))
    return out


def _require_persisted_arms(spec: SourceSpec, key: TripleKey,
                            arms: tuple[tuple[str, str], ...]) -> None:
    """What the FILES prove: every required arm has a record, and it finished."""
    names = tuple(name for name, _ in arms)
    missing = tuple(arm for arm in REQUIRED_ARMS if arm not in names)
    extra = tuple(name for name in names if name not in REQUIRED_ARMS)
    if missing or extra:
        raise CohortError(
            f"source {spec.label!r} ({spec.run_dir}): complete triple {key.case_id}|{key.repeat} "
            f"declares {list(REQUIRED_ARMS)} on its row, but <run>.arms.jsonl holds {list(names)} "
            f"— missing {list(missing)}, unknown {list(extra)}")
    unfinished = tuple(f"{name}={termination}" for name, termination in arms
                       if termination != ARM_DONE)
    if unfinished:
        raise CohortError(
            f"source {spec.label!r} ({spec.run_dir}): persisted arms of complete triple "
            f"{key.case_id}|{key.repeat} did not finish: {unfinished}")


def _case_fingerprints(corpus: tuple[CaseV5, ...], spec: SourceSpec) -> tuple[tuple[str, str], ...]:
    """One corpus by id and definition hash; a duplicate id with two different
    definitions is refused rather than merged under one."""
    out: dict[str, str] = {}
    for case in corpus:
        case_id = case.base.id
        digest = _fingerprint(case_v5_to_json(case))
        previous = out.get(case_id)
        if previous is not None and previous != digest:
            raise CohortError(
                f"source {spec.label!r} ({spec.run_dir}): corpus carries {case_id!r} twice "
                f"with different definitions ({previous[:12]} and {digest[:12]})")
        out[case_id] = digest
    return tuple(sorted(out.items()))


def _source_of(spec: SourceSpec) -> SourceProvenance:
    """One run directory, read once, into the population and its record."""
    run_dir = spec.run_dir
    try:
        run_id = report.run_id_of(run_dir)
    except report.ReportError as error:
        raise CohortError(f"source {spec.label!r}: {error}") from error

    inputs: list[tuple[str, str]] = []
    for name in INPUT_FILES:
        path = records.run_file(run_dir, run_id, name)
        if not path.exists():
            raise CohortError(f"source {spec.label!r} ({run_dir}): no {path.name} — a source "
                              f"whose inputs cannot be hashed cannot be composed")
        inputs.append((name.replace(records.RUN_PLACEHOLDER, run_id), _file_sha256(path)))
    input_sha256 = tuple(inputs)

    triple_path = records.run_file(run_dir, run_id, "<run>.triples.jsonl")
    attempts = tuple(_attempt(row, triple_path) for row in records.read_rows(triple_path))
    by_key: dict[TripleKey, list[_Attempt]] = {}
    for attempt in attempts:
        by_key.setdefault(attempt.key, []).append(attempt)

    complete_keys: list[TripleKey] = []
    for key in sorted(by_key):
        complete = [one for one in by_key[key] if one.status == COMPLETE_STATUS]
        if len(complete) > 1:
            raise CohortError(
                f"source {spec.label!r} ({run_dir}): duplicate complete key "
                f"{key.case_id}|{key.repeat} — {len(complete)} complete rows carry it; the "
                f"composition cannot pick one attempt, and choosing the «best» is forbidden")
        for one in complete:
            _require_whole_row(one, spec)
            complete_keys.append(key)

    persisted = _persisted_arms(run_dir, run_id)
    for key in complete_keys:
        _require_persisted_arms(spec, key, persisted.get(key, ()))

    corpus = report.v5_corpus(run_dir)
    case_fingerprints = _case_fingerprints(corpus, spec)
    half = report.observations_of(run_dir, (), {case.base.id: case for case in corpus})

    observed: dict[TripleKey, RunObservation] = {}
    for one in half.observations:
        key = TripleKey(one.case.base.id, one.repeat)
        if key in observed:
            raise CohortError(f"source {spec.label!r} ({run_dir}): two observations for "
                              f"{key.case_id}|{key.repeat}")
        observed[key] = one
    orphan = tuple(sorted(key for key in observed if key not in by_key))
    if orphan:
        raise CohortError(
            f"source {spec.label!r} ({run_dir}): arm records without a triple row for "
            f"{[f'{key.case_id}|{key.repeat}' for key in orphan]} — the cost and the status of "
            f"those attempts were never written, so neither efficacy nor spend can count them")

    holes = {name.split(" (", 1)[0] for name in half.hopless + half.stopped}
    for key in complete_keys:
        if key not in observed:
            name = f"{key.case_id}|{key.repeat}"
            detail = " (the arm did not finish)" if name in holes else ""
            raise CohortError(
                f"source {spec.label!r} ({run_dir}): complete triple {name} has no hop record in "
                f"<run>.hops.jsonl{detail} — a triple with no hop is not a measured effect")

    selected = tuple(observed[key] for key in complete_keys)
    exclusions = tuple(
        ExcludedAttempt(source=spec.label, run_id=run_id, key=one.key, status=one.status,
                        reason=one.reason, arms=tuple(name for name, _ in one.arms),
                        cost_usd=one.cost_usd, judge_cost_usd=one.judge_cost_usd,
                        turn_residual=one.turn_residual)
        for one in attempts if one.status != COMPLETE_STATUS)
    efficacy_usd = sum(one.cost_usd for one in attempts if one.status == COMPLETE_STATUS)
    excluded_usd = sum(one.cost_usd for one in attempts if one.status != COMPLETE_STATUS)
    triples_usd = sum(one.cost_usd for one in attempts)
    ledger = report._ledger_total(records.run_file(run_dir, run_id, "<run>.spend.tsv"))
    return SourceProvenance(
        label=spec.label,
        run_dir=run_dir,
        run_id=run_id,
        config=_configuration(report.meta_of(run_dir, run_id),
                              records.run_file(run_dir, run_id, "<run>.meta.json")),
        complete_keys=tuple(complete_keys),
        observations=selected,
        excluded=exclusions,
        spend=SourceSpend(
            label=spec.label, run_id=run_id, triples_usd=triples_usd, efficacy_usd=efficacy_usd,
            excluded_usd=excluded_usd, judge_usd=sum(one.judge_cost_usd for one in attempts),
            ledger_usd=ledger, ledger_delta_usd=None if ledger is None else ledger - triples_usd),
        rows=len(attempts),
        duplicate_attempts=sum(len(rows) - 1 for rows in by_key.values()),
        retried_keys=tuple(sorted(key for key, rows in by_key.items() if len(rows) > 1)),
        corpus_cases=len(corpus),
        case_fingerprints=case_fingerprints,
        corpus_v5_sha256=dict(input_sha256)["corpus.v5.json"],
        input_sha256=input_sha256)


def _read_source(spec: SourceSpec) -> SourceProvenance:
    """`_source_of` with the source's name on every failure, so a row three
    directories deep names the directory and not only the field."""
    try:
        return _source_of(spec)
    except (records.RecordError, report.ReportError) as error:
        raise CohortError(f"source {spec.label!r} ({spec.run_dir}): {error}") from error


def _config_groups(provenances: tuple[SourceProvenance, ...]) -> tuple[ConfigGroup, ...]:
    grouped: dict[str, list[SourceProvenance]] = {}
    for one in provenances:
        grouped.setdefault(one.config.fingerprint(), []).append(one)
    return tuple(ConfigGroup(fingerprint=digest,
                             labels=tuple(one.label for one in members),
                             configuration=members[0].config)
                 for digest, members in sorted(grouped.items()))


def _corpus_cases(provenances: tuple[SourceProvenance, ...]) -> tuple[CorpusCase, ...]:
    """Every case id any source declares, its definition hash and its sources.
    Two sources disagreeing about one id is a refusal; agreement across a SUBSET
    is not required, because the making-up runs legitimately ran 3 of 1800."""
    seen: dict[str, tuple[str, list[str]]] = {}
    for one in provenances:
        for case_id, digest in one.case_fingerprints:
            entry = seen.get(case_id)
            if entry is None:
                seen[case_id] = (digest, [one.label])
                continue
            if entry[0] != digest:
                raise CohortError(
                    f"corpus case {case_id!r} is defined differently in {entry[1][0]!r} and "
                    f"{one.label!r} ({entry[0][:12]} vs {digest[:12]}) — the two directories "
                    f"measured different cases under one id and cannot share a population")
            entry[1].append(one.label)
    return tuple(CorpusCase(case_id=case_id, definition_sha256=digest, sources=tuple(labels))
                 for case_id, (digest, labels) in sorted(seen.items()))


def selection_of(cohort: Cohort) -> tuple[tuple[TripleKey, str], ...]:
    """Which source every efficacy key came from, source-label then key order;
    derived from the sources, so the two cannot disagree after hand edits."""
    return tuple((key, one.label) for one in cohort.sources for key in one.complete_keys)


def compose_cohort(sources: tuple[SourceSpec, ...]) -> Cohort:
    """Read every source once and return ONE completed cohort. Sources are
    ordered by label, never by the caller's order: the fingerprint must pin the
    data, not the order the paths were typed in."""
    if not sources:
        raise CohortError("compose_cohort: no sources — an empty cohort is not a cohort")
    labels = tuple(one.label for one in sources)
    if len(set(labels)) != len(labels):
        duplicates = sorted({label for label in labels if labels.count(label) > 1})
        raise CohortError(f"compose_cohort: repeated source label(s) {duplicates} — a label names "
                          f"one directory in every table below")
    provenances = tuple(_read_source(one) for one in sorted(sources, key=lambda one: one.label))

    owner: dict[TripleKey, str] = {}
    for one in provenances:
        for key in one.complete_keys:
            previous = owner.get(key)
            if previous is not None:
                raise CohortError(
                    f"duplicate complete key {key.case_id}|{key.repeat}: sources {previous!r} and "
                    f"{one.label!r} both claim it — the cohort is exactly one source per key")
            owner[key] = one.label

    fingerprint = _fingerprint({
        "version": MANIFEST_VERSION,
        "sources": tuple({
            "label": one.label, "run_id": one.run_id, "config": one.config.fingerprint(),
            "corpus_v5_sha256": one.corpus_v5_sha256, "input_sha256": one.input_sha256,
            "complete_keys": tuple((key.case_id, key.repeat) for key in one.complete_keys)}
            for one in provenances)})
    return Cohort(
        version=MANIFEST_VERSION,
        fingerprint=fingerprint,
        observations=tuple(sorted((one for source in provenances for one in source.observations),
                                  key=lambda one: (one.case.base.id, one.repeat))),
        sources=provenances,
        exclusions=tuple(one for source in provenances for one in source.excluded),
        config_groups=_config_groups(provenances),
        corpus_cases=_corpus_cases(provenances),
        spend=CohortSpend(
            triples_usd=sum(one.spend.triples_usd for one in provenances),
            efficacy_usd=sum(one.spend.efficacy_usd for one in provenances),
            excluded_usd=sum(one.spend.excluded_usd for one in provenances),
            judge_usd=sum(one.spend.judge_usd for one in provenances),
            ledger_usd=(None if any(one.spend.ledger_usd is None for one in provenances)
                        else sum(one.spend.ledger_usd for one in provenances
                                 if one.spend.ledger_usd is not None))))


def _key_json(key: TripleKey) -> dict[str, object]:
    return {"case_id": key.case_id, "repeat": key.repeat}


def _config_json(config: RunConfiguration) -> dict[str, object]:
    return {"model": config.model, "judge_model": config.judge_model, "tier": config.tier,
            "repeats": config.repeats, "prompt_sha256": config.prompt_sha256,
            "ceiling_usd": config.ceiling_usd, "provider": [list(p) for p in config.provider],
            "limits": [list(p) for p in config.limits], "gateway": [list(p) for p in config.gateway]}


def _money(value: float) -> float:
    """Rounded where the ledger rounds, so the file and the ledger cannot
    disagree by a cent."""
    return round(value, 6)


def cohort_to_json(cohort: Cohort) -> dict[str, object]:
    """The manifest as data, carrying the version it was written under. It holds
    case ids, labels, hashes, configurations, prices and reasons — no observation
    and no corpus value, because a manifest is a file that gets copied and
    quoted."""
    return {
        "version": cohort.version,
        "fingerprint": cohort.fingerprint,
        "uniform_experiment": cohort.uniform_experiment,
        "selection": [{**_key_json(key), "source": label} for key, label in selection_of(cohort)],
        "spend": {"triples_usd": _money(cohort.spend.triples_usd),
                  "efficacy_usd": _money(cohort.spend.efficacy_usd),
                  "excluded_usd": _money(cohort.spend.excluded_usd),
                  "judge_usd": _money(cohort.spend.judge_usd),
                  "ledger_usd": (None if cohort.spend.ledger_usd is None
                                 else _money(cohort.spend.ledger_usd))},
        "config_groups": [{"fingerprint": group.fingerprint, "labels": list(group.labels),
                           "configuration": _config_json(group.configuration)}
                          for group in cohort.config_groups],
        "sources": [{
            "label": one.label, "run_dir": str(one.run_dir), "run_id": one.run_id,
            "config": _config_json(one.config),
            "complete": [_key_json(key) for key in one.complete_keys],
            "rows": one.rows, "duplicate_attempts": one.duplicate_attempts,
            "retried_keys": [_key_json(key) for key in one.retried_keys],
            "corpus_cases": one.corpus_cases, "corpus_v5_sha256": one.corpus_v5_sha256,
            "input_sha256": [list(pair) for pair in one.input_sha256],
            "spend": {"triples_usd": _money(one.spend.triples_usd),
                      "efficacy_usd": _money(one.spend.efficacy_usd),
                      "excluded_usd": _money(one.spend.excluded_usd),
                      "judge_usd": _money(one.spend.judge_usd),
                      "ledger_usd": (None if one.spend.ledger_usd is None
                                     else _money(one.spend.ledger_usd)),
                      "ledger_delta_usd": (None if one.spend.ledger_delta_usd is None
                                           else _money(one.spend.ledger_delta_usd))}}
            for one in cohort.sources],
        "exclusions": [{**_key_json(one.key), "source": one.source, "run_id": one.run_id,
                        "status": one.status, "reason": one.reason, "arms": list(one.arms),
                        "cost_usd": _money(one.cost_usd),
                        "judge_cost_usd": _money(one.judge_cost_usd),
                        "turn_residual": one.turn_residual}
                       for one in cohort.exclusions],
        "corpus_cases": [{"case_id": one.case_id, "definition_sha256": one.definition_sha256,
                          "sources": list(one.sources)} for one in cohort.corpus_cases],
    }
