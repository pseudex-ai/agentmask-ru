"""THE FROZEN ORACLE — the scoring path that no mutable engine can move.

    from bench.agentpii5 import frozen_oracle
    score = frozen_oracle.score_artifacts(cases, saved_rows)

WHY THIS FILE EXISTS (M04). A benchmark's oracle must not be movable by the
thing it scores. `bench/agentpii5` is arithmetic over records and imports no
`pseudex`, but the wider oracle it lives inside still reaches the engine LAZILY:
v4's taxonomy calls v3 `classify_break`, whose street comparison imports
`pseudex.address.register_spelling` INSIDE the function, against a leased
register that changes with the tuning. Score a saved run before and after an
engine edit and «the gateway improved» and «the scorer changed its mind» are the
same number, with nothing in the repository able to tell them apart.

THE ANSWER IS TWO RULES, and neither is a refactor of the engine.

  1. **The repair verdict is FROZEN DATA.** `RepairTable` is a witness captured
     ONCE, from one engine, at artifact-construction time. `repair_verdict`
     reads the witness and never asks the engine anything. A pair with no
     witness answers `None` — UNMEASURED — and never `False`, because «nobody
     looked» and «the street was not repaired» are different facts and a scorer
     that merges them pays the gateway for the oracle's silence.
  2. **The scoring process runs behind a firewall.** `forbid_engine` blocks
     every `pseudex` import for the duration and `assert_engine_free` refuses a
     process that already holds one. A number produced inside it cannot depend
     on engine code, because engine code cannot be loaded inside it.

WHAT THIS IS NOT. It is not a claim that the ENGINE is untrustworthy: the
register spelling is the engine's own rule and asking it once is right. What is
wrong is asking it at SCORE time, when the answer must be the one the run was
scored with. Freezing the answer is the whole change.

NO FIXTURE LITERALS. Nothing here names a case, a type's value or a corpus
literal; `test_frozen_oracle.test_no_corpus_literal_in_the_scorer` reads this
file back and demands it stay that way. A scorer that recognises a fixture is a
scorer that can be tuned against one.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.abc
import json
import pathlib
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Iterator

from bench.agentpii5 import contracts, metrics, observe, records, schema
from bench.agentpii5.contracts import CaseV5, Line, RunObservation

# Bumped whenever the frozen semantics change, so a saved score can always name
# the oracle that produced it. A number with no oracle version is a number that
# cannot be re-checked, which is the disease this file was written against.
# m04-frozen-2: the artifact digest now covers the SCORED SAVED HOPS and the
# repair WITNESSES as well as the corpus ids and the rows, so it names the
# population the lines were computed over and not merely the files they sat in.
# m04-frozen-3: the corpus half of the digest is the corpus CONTENT — every case
# through the canonical `schema.case_v5_to_json`, ordered by its own bytes — and
# not its id list, because `overmask` counts `negatives`, `consistency`/
# `stability` enumerate `pii` and the axes read `register`/`messages`: a corpus
# rewritten under the same ids moved printed numbers and 47 axis cells while the
# id-only address sat still (review F1). `artifact_digest` also DEMANDS an
# explicit population, so the defaults that let a caller mint a second address
# under this one version are gone (review F2).
FROZEN_ORACLE_VERSION: str = "m04-frozen-3"
FORBIDDEN_IMPORT_PREFIX: str = "pseudex"

# The single-arm lines: every metric that reads ONE arm's records, which is the
# whole of what an artifact-only oracle can print. Derived from the registry and
# never restated, so a new metric is either here or absent from both places.
SINGLE_ARM_METRICS: tuple[str, ...] = tuple(
    name for name in contracts.METRIC_NAMES if name in metrics.METRIC_FUNCTIONS)


class EngineDependencyError(RuntimeError):
    """The oracle was asked to run where the mutable engine is reachable."""


class FrozenOracleError(ValueError):
    """A saved artifact the oracle cannot score, named by what is missing."""


# --- rule 2: the firewall ------------------------------------------------------------

def engine_modules_loaded() -> frozenset[str]:
    """Every `pseudex` module currently importable from `sys.modules`."""
    return frozenset(
        name for name in sys.modules
        if name == FORBIDDEN_IMPORT_PREFIX or name.startswith(FORBIDDEN_IMPORT_PREFIX + "."))


def assert_engine_free() -> None:
    """Refuse to score where the engine is loaded. A red instrument, not a note."""
    loaded = engine_modules_loaded()
    if loaded:
        raise EngineDependencyError(
            f"the engine is loaded ({sorted(loaded)}); a frozen score must be produced "
            f"in a process that cannot import it")


class _EngineBlocker(importlib.abc.MetaPathFinder):
    """A finder that raises on `pseudex` and its submodules, at the front of
    `sys.meta_path`, so the import fails in the importing statement itself."""

    def find_spec(self, fullname: str, path: object = None,
                  target: object = None) -> None:
        if fullname == FORBIDDEN_IMPORT_PREFIX or fullname.startswith(
                FORBIDDEN_IMPORT_PREFIX + "."):
            raise EngineDependencyError(
                f"the frozen oracle forbade the engine import of {fullname!r}")
        return None


@contextlib.contextmanager
def forbid_engine(remove_loaded: bool = True) -> Iterator[None]:
    """Block every `pseudex` import for the duration of the block.

    The already-loaded modules are REMOVED and not put back: a restored module is
    a second route to the same mutable code, the block is what makes the
    measurement independent, and a caller who needs the engine afterwards starts
    a process that may hold it. `remove_loaded=False` is for a caller that
    wants the import hook alone and takes responsibility for the rest.
    """
    if remove_loaded:
        for name in engine_modules_loaded():
            sys.modules.pop(name, None)
    blocker = _EngineBlocker()
    sys.meta_path.insert(0, blocker)
    try:
        yield
    finally:
        with contextlib.suppress(ValueError):
            sys.meta_path.remove(blocker)


# --- rule 1: the repair verdict as frozen data ---------------------------------------

@dataclass(frozen=True)
class RepairWitness:
    """One street pair, and the answer the engine gave the day it was frozen.

    `repaired` is the engine's judgement — «`restored` is `expected` with one
    mistyped street word replaced by the register spelling» — captured once so
    that re-scoring a saved run cannot change it.
    """

    expected: str
    restored: str
    repaired: bool

    @property
    def key(self) -> tuple[str, str]:
        return (self.expected, self.restored)

    def to_json(self) -> dict[str, object]:
        return {"expected": self.expected, "restored": self.restored,
                "repaired": self.repaired}

    @classmethod
    def from_json(cls, row: Mapping[str, object]) -> RepairWitness:
        expected = row.get("expected")
        restored = row.get("restored")
        repaired = row.get("repaired")
        if not isinstance(expected, str) or not isinstance(restored, str):
            raise FrozenOracleError(f"RepairWitness: expected/restored must be strings, "
                                    f"found {expected!r}/{restored!r}")
        if not isinstance(repaired, bool):
            raise FrozenOracleError(f"RepairWitness: repaired must be a bool, found {repaired!r}")
        return cls(expected=expected, restored=restored, repaired=repaired)


@dataclass(frozen=True)
class RepairTable:
    """The frozen witnesses of one corpus, keyed by the pair they answer for."""

    witnesses: tuple[RepairWitness, ...] = ()

    @property
    def by_key(self) -> dict[tuple[str, str], bool]:
        return {witness.key: witness.repaired for witness in self.witnesses}

    def to_json(self) -> dict[str, object]:
        return {"version": FROZEN_ORACLE_VERSION,
                "witnesses": [witness.to_json() for witness in self.witnesses]}

    def write(self, path: pathlib.Path) -> None:
        path.write_text(json.dumps(self.to_json(), ensure_ascii=False, sort_keys=True,
                                   indent=1) + "\n", encoding="utf-8")

    @classmethod
    def read(cls, path: pathlib.Path) -> RepairTable:
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw.get("witnesses") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            raise FrozenOracleError(f"{path}: no `witnesses` list")
        return cls(witnesses=tuple(RepairWitness.from_json(row) for row in rows
                                   if isinstance(row, dict)))


def repair_verdict(expected: str, restored: str, table: RepairTable) -> bool | None:
    """`True`/`False` from the FROZEN witness, `None` when there is none.

    It never calls `register_spelling` and never imports anything: the pair was
    already judged, once, by whoever built the artifact. `None` is a live
    reading of «unmeasured» which the caller must print as such — collapsing it
    to `False` is how a saved run silently becomes a clean one.
    """
    return table.by_key.get((expected, restored))


def freeze_repairs(pairs: Iterable[tuple[str, str]],
                   spell: Callable[[str], str]) -> RepairTable:
    """Capture the engine's verdict for each pair, ONCE, at freeze time.

    `spell` is the engine's `register_spelling` (or any callable of that shape)
    passed IN by the caller: this module holds no reference to the engine, so
    the capture can happen in a process that may import it and the re-scoring
    cannot happen in one that may not. The vocabulary is the pair's words, so a
    pair the engine cannot speak about is frozen as `False` exactly as the
    engine's own comparison would have answered it live.
    """
    witnesses: list[RepairWitness] = []
    for expected, restored in pairs:
        witnesses.append(RepairWitness(expected=expected, restored=restored,
                                       repaired=_engine_agrees(expected, restored, spell)))
    return RepairTable(witnesses=tuple(witnesses))


def _engine_agrees(expected: str, restored: str, spell: Callable[[str], str]) -> bool:
    """The engine's `_street_repaired` rule, applied once and never again.

    Word by word, equal words skipped, a differing word repaired only when the
    register vouches for it and at least one word actually differed. The rule is
    the engine's; the STATE it consults is the argument, so this function cannot
    reach a leased register on its own.
    """
    left, right = expected.split(), restored.split()
    if len(left) != len(right):
        return False
    fixed = 0
    for one, other in zip(left, right):
        if one == other:
            continue
        try:
            vouched = spell(one)
        except Exception:  # noqa: BLE001 — a bundle-less engine answers nothing, as in v3
            return False
        if vouched != other.lower():
            return False
        fixed += 1
    return fixed > 0


# --- the frozen score ----------------------------------------------------------------

@dataclass
class FrozenScore:
    """The lines a saved artifact prints, and the digest of the bytes they came from."""

    lines: Mapping[str, Line]
    digest: str
    cases: int
    rows: int
    oracle_version: str = FROZEN_ORACLE_VERSION
    # The paired LOC repairs the artifact carried, as FROZEN data. A pair with
    # no witness counts in `unmeasured` and is printed as such: an artifact with
    # no repair table is not an artifact whose streets all round-tripped.
    repairs_measured: int = 0
    repairs_unmeasured: int = 0

    def rates(self) -> dict[str, float]:
        return {name: line.rate for name, line in self.lines.items()}


# --- the repair table ON DISK, so the report can pass it as DATA ----------------------

def repairs_path(run_dir: pathlib.Path) -> pathlib.Path:
    """Where a run keeps its captured repair witnesses. Beside the hops, never
    inside a corpus file: the witness is about THIS run's artifacts."""
    return run_dir / "repairs.json"


def read_repairs(run_dir: pathlib.Path) -> RepairTable:
    """The run's captured witnesses, or an EMPTY table.

    An absent file is not an error and not a clean bill: the empty table makes
    every pair `None` — unmeasured — which the report prints as a count. The
    alternative (raising, or defaulting to `False`) either refuses a legacy run
    or pays the gateway for the oracle's silence.
    """
    path = repairs_path(run_dir)
    if not path.exists():
        return RepairTable()
    return RepairTable.read(path)


def capture_run_repairs(run_dir: pathlib.Path,
                        pairs: Iterable[tuple[str, str]],
                        spell: Callable[[str], str]) -> pathlib.Path:
    """Freeze a run's LOC repairs ONCE, at production, beside its artifacts.

    THIS IS THE PRODUCTION WRITE, and it is deliberately separate from scoring:
    the engine is asked here, exactly once, by whoever produced the run, and the
    answer is persisted as versioned `RepairTable` data that the scorer later
    READS. The alternative — asking `register_spelling` while scoring — is the
    defect M04 exists to remove: a saved number would move with the engine and
    nothing on disk could tell «the gateway improved» from «the scorer changed
    its mind».

    `spell` is the engine's `register_spelling`, passed IN. This module holds no
    reference to the engine and imports none: the capture may run in a process
    that holds the engine, and the re-scoring must run in one that cannot reach
    it.

    The call site belongs to the run's producer (the harness that owns the
    engine at run time); a report only reads. Until that one call is wired, every
    real run's LOC pairs stay UNMEASURED — printed as «не измерено», which is
    honest and never a clean bill.
    """
    table = freeze_repairs(pairs, spell)
    path = repairs_path(run_dir)
    table.write(path)
    return path


def _canonical_json(value: object) -> str:
    """The ONE serialisation every half of the address goes through, so two
    halves cannot disagree about a separator and a digest cannot depend on which
    `json.dumps` flags the caller happened to remember."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), default=str)


def _jsonable(value: object) -> object:
    """Every `set`/`frozenset` → a SORTED list, recursively.

    `json.dumps` can only fall back to `default=str` for a set, and `str` of a
    set iterates in HASH order: one population would mint two addresses in two
    processes with different `PYTHONHASHSEED`, and nothing on disk could explain
    why. No case field is a set today — this is the guard that stops a field
    added tomorrow from silently re-opening the hole. `artifact_digest` is a
    content ADDRESS, so «the same bytes» has to mean it."""
    if isinstance(value, (set, frozenset)):
        return sorted((_jsonable(one) for one in value), key=_canonical_json)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(one) for key, one in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(one) for one in value]
    return value


def corpus_content(cases: Sequence[CaseV5]) -> list[object]:
    """The corpus HALF of the digest: every case through the canonical
    `schema.case_v5_to_json`, ordered by its own serialised form.

    THE ID LIST IS NOT THE POPULATION. Every printed line is scored against the
    case OBJECT — `overmask` counts `negatives`, `consistency`/`stability`
    enumerate `pii`, the axes read `register`, `behaviour`, `messages` and
    `returns` — so a corpus rewritten under the same ids is another measurement
    of another population, and an address that folds the corpus down to its ids
    hands both measurements one versioned number (review F1).

    The order is the CONTENT's, never the caller's: the same cases in another
    order are the same population. The sort key is the serialised case and not
    the id alone, because a duplicated id would tie and leave the order — and so
    the address — up to the caller after all."""
    canon = [_jsonable(schema.case_v5_to_json(case)) for case in cases]
    return sorted(canon, key=_canonical_json)


def artifact_digest(cases: Sequence[CaseV5], rows: Sequence[Mapping[str, object]],
                    observations: Sequence[RunObservation],
                    repairs: RepairTable | None) -> str:
    """Content address of (corpus CONTENT, saved rows, the SCORED saved hops, the
    repair witnesses).

    ALL FOUR HALVES, because a line is scored against a POPULATION and not
    against a directory. `cases` + `rows` alone named the files but not what was
    counted from them: the same rows with one case's `<run>.hops.jsonl` rows
    absent is another measurement — the report scored the saved half while the
    digest sat still — and the same hops judged against another `RepairTable` is
    another repair verdict. A number a reader cannot tie to the hops it was
    computed over is the thing this module exists to refuse (OBS).

    THE CORPUS IS HASHED AS CONTENT, NOT AS AN ID LIST (F1). `corpus_content`
    carries every case through the canonical `schema.case_v5_to_json`, so
    `negatives`, `pii`, `register` and `messages` are in the address — the four
    fields a printed total or an axis cell reads.

    THE POPULATION IS A REQUIRED ARGUMENT (F2). `observations` and `repairs` used
    to default to empty, so `artifact_digest(cases, rows)` minted a SECOND
    address under the same `FROZEN_ORACLE_VERSION` as the scored path, and a
    digest quoted out of context could not be told from the population-scored
    one. A caller that holds only the artifacts must now SAY it scored no hops —
    `artifact_digest(cases, rows, (), None)` — which is a statement about a
    population instead of a default that hides one."""
    table = repairs if repairs is not None else RepairTable()
    blob = _canonical_json(_jsonable(
        {"corpus": corpus_content(cases),
         "rows": [dict(row) for row in rows],
         "hops": [records.hop_observation_to_json(hop)
                  for one in observations for hop in one.hops],
         "repairs": [witness.to_json() for witness in table.witnesses]}))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def repair_pairs(observations: Sequence[RunObservation]) -> tuple[tuple[str, str], ...]:
    """Every LOC pair the run actually produced, as (expected, restored).

    The pair comes from the OBSERVATION, not from the witness file: the artifact
    says which streets it restored, and the table only answers for them. A table
    that named its own pairs would count witnesses for hops the run never made
    and would go on printing them after the corpus changed."""
    pairs: list[tuple[str, str]] = []
    for one in observations:
        for hop in one.hops:
            if hop.pii_type != "LOC" or hop.status != "observed" or not hop.produced:
                continue
            pairs.append((hop.reference, hop.produced))
    return tuple(pairs)


def score_observations(observations: Sequence[RunObservation],
                       cases: Sequence[CaseV5], rows: Sequence[Mapping[str, object]],
                       repairs: RepairTable | None = None) -> FrozenScore:
    """Every single-arm line over observations, plus the repair verdicts READ
    FROM THE FROZEN TABLE — the entry point `report.read_parts` calls.

    `repairs` is DATA, passed in by the caller: this function cannot capture a
    witness and never touches the engine. A LOC pair with no witness counts in
    `repairs_unmeasured` and answers `None`; nothing here turns that into
    `False`, because «nobody froze this pair» is not «the street was not
    repaired».

    THE DIGEST NAMES WHAT WAS SCORED. It covers the corpus CONTENT the lines
    were scored against (through the canonical `schema.case_v5_to_json`), `seen`
    and the witness table, not only the corpus ids and rows the caller happened
    to hold: the report scores the SAVED hops, which on a run with a hole are
    fewer than the rows, and a digest over the ids and rows alone left both that
    difference and every same-id corpus edit unrecorded (OBS, F1)."""
    seen = tuple(observations)
    lines = {name: metrics.METRIC_FUNCTIONS[name](seen) for name in SINGLE_ARM_METRICS}
    table = repairs if repairs is not None else RepairTable()
    measured = 0
    unmeasured = 0
    for expected, restored in repair_pairs(seen):
        if repair_verdict(expected, restored, table) is None:
            unmeasured += 1
        else:
            measured += 1
    return FrozenScore(lines=lines, digest=artifact_digest(cases, rows, seen, table),
                       cases=len(cases), rows=len(rows),
                       repairs_measured=measured, repairs_unmeasured=unmeasured)


def score_artifacts(cases: Sequence[CaseV5], rows: Sequence[Mapping[str, object]],
                    repairs: RepairTable | None = None) -> FrozenScore:
    """Every single-arm line over SAVED rows, with the engine never consulted.

    The rows are decoded and observed exactly as `report.observations_of` does;
    the arithmetic is the package's own `metrics`. Nothing here re-derives a hop
    and nothing here imports the engine — that is the whole product of M04.
    """
    by_id = {case.base.id: case for case in cases}
    observations: list[RunObservation] = []
    for row in rows:
        run = records.arm_v5_from_record(dict(row))
        case = by_id.get(run.base.case_id)
        if case is None:
            raise FrozenOracleError(
                f"a saved row names case {run.base.case_id!r}, which this corpus does not "
                f"carry; the artifacts and the corpus are not the same run")
        observations.append(observe.observe(case, run, None, None))
    return score_observations(observations, cases, rows, repairs)


def main() -> int:
    """Score a saved run directory, engine-free, and print the lines.

        python3 -m bench.agentpii5.frozen_oracle <run_dir>
    """
    import argparse
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=pathlib.Path)
    args = parser.parse_args()
    run_dir: pathlib.Path = args.run_dir
    from bench.agentpii5.report import v5_cases
    with forbid_engine():
        assert_engine_free()
        cases = list(v5_cases(run_dir).values())
        rows = records.merged_v5_records(run_dir)
        score = score_artifacts(cases, rows)
    for name in SINGLE_ARM_METRICS:
        line = score.lines[name]
        print(f"  {name:<24} {line.hits}/{line.total}")
    print(f"frozen_oracle {score.oracle_version}: {score.rows} rows, digest {score.digest[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
