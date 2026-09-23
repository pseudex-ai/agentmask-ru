"""Cases that have stopped measuring anything — the case defect a run cannot
tell from a product defect (пункт 21 ТЗ).

    cd prototype && source .venv/bin/activate
    python3 -m bench.agentpii5.quarantine <каталог прогона> <каталог> <каталог>
    python3 -m bench.agentpii5.quarantine --runs-file bench/agentpii5/runs.json

WHAT A CASE FLAPPING AT ALL THREE ARMS MEANS. The gateway arm alone behaving
differently from run to run is a PRODUCT finding — that is what the benchmark is
for. All three arms flapping, under the same models on the same corpus, is a
statement about the CASE: it asks the agent something with no stable answer
(two tools fit equally, the wording invites either of two calls), and it will go
on adding noise to every family share it sits in for as long as it is in the
corpus. Three consecutive runs rather than two, because a single pair separates
a flapping case from an ordinary coin-flip by nothing at all.

IT PRINTS AND IT NEVER MARKS. Removing or annotating a case changes the corpus
and therefore every number computed on it, which is the owner's decision
(§7.2); a tool that quarantined cases by itself would silently shrink the
family whose disagreement it was reporting. Nothing in this module writes a
file — `test_quarantine.test_nothing_here_writes` reads this module's own AST
to keep it that way.

WHAT IS COMPARED, AND WHAT IS DELIBERATELY NOT. The fingerprint is WHAT THE ARM
DID: how it terminated, which tools it called in which order, which leaves it
filled, whether each call parsed, whether it answered at all. It is NOT what the
agent wrote: the substitutes are minted fresh by every run, so a fingerprint
over values would call every case unstable, and the exact wording of a reply
differs on every sampling of any model — a case is not defective because the
agent phrased its sentence differently. No corpus value, no reply text and no
substitute reaches the output: ids, hashes and counts only.

NO MODEL, NO NETWORK, NO KEYS: the files of runs that already happened.
"""
import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from bench.agentpii4.schema import ARMS, EXCLUDED_TERMINATIONS
from bench.agentpii5 import records as r

# Three consecutive runs is the ТЗ's number (§7.2) and it is the smallest one
# that means anything: with two, one arm that answered differently once is
# «unstable» at every arm by definition.
WINDOW: int = 3
KIND: str = "arm row"
# The key `runs.json` (§1.2) names a run's directory under. It was a SET of three
# spellings while the registry did not exist yet; `runinfo.RunRecord` landed with
# one field, `run_dir`, so the set is that one name. A reader that went on
# accepting two more spellings would accept a registry nobody writes, and the
# refusal below — BY NAME, listing what the row does carry — is what tells a
# reader whose file is genuinely older that it is.
REGISTRY_DIR_KEYS: tuple[str, ...] = ("run_dir",)
# Registry states whose runs this tool reads past. `runinfo.RUN_STATES` is
# («finished», «interrupted»); an interrupted run has no `meta.json`, so it
# carries no conditions to compare under — and §1.2 requires its row to stay.
SKIPPED_STATES: frozenset[str] = frozenset({"interrupted"})
# What makes two runs comparable at all. A case that behaves differently under
# another model, another judge or another corpus has told us nothing about
# itself — and these four are exactly what `meta.json` records about a run.
CONDITION_KEYS: tuple[str, ...] = ("digest", "model", "judge_model", "tier")


class QuarantineError(ValueError):
    """A run directory that cannot be read as a run.

    Named and raised rather than skipped: a directory silently left out of the
    comparison would make «no unstable cases» mean «two of the three runs were
    unreadable», and those two readings are indistinguishable in the printed
    line.
    """


@dataclass(frozen=True)
class RunReading:
    """One finished run, reduced to what this question needs.

    `behaviour` is keyed by (case id, arm) and holds the DISTINCT fingerprints
    the repeats of that arm produced — a set rather than a list, because K
    repeats agreeing is the same evidence whether K is 2 or 5, and the count of
    repeats belongs to the run's own report.
    """

    run_id: str
    directory: Path
    finished: str
    conditions: tuple[tuple[str, str], ...]
    behaviour: dict[tuple[str, str], frozenset[str]]
    labels: dict[str, tuple[str, str]]


@dataclass(frozen=True)
class Suspect:
    """A case that flapped at every arm across a window of consecutive runs."""

    case_id: str
    kind: str
    register: str
    runs: tuple[str, ...]
    per_arm: tuple[tuple[str, int], ...]
    windows: int


# --- reading a run ---------------------------------------------------------------------

def _text(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str):
        raise QuarantineError(f"{KIND}.{key}: expected a string, found {value!r}")
    return value


def _list(row: dict[str, object], key: str) -> list[object]:
    value = row.get(key)
    if not isinstance(value, list):
        raise QuarantineError(f"{KIND}.{key}: expected a list, found {value!r}")
    return value


def behaviour_fingerprint(row: dict[str, object]) -> str:
    """What this arm DID, as one short hash.

    THE SHAPE IS THE VERDICT AND THE TEXT IS NOT. Two runs of one case differ in
    every substitute (a vault is minted per run) and in the wording of every
    reply (any sampling does that), and neither is a property of the case. What
    is: the termination, the tools called in order, the leaves each call filled,
    whether the call parsed, whether the agent refused and under which rule, how
    many records it wrote and whether it answered at all. A case whose agent
    calls `create_order` in one run and `update_order` in the next has been
    asked a question with two right answers.

    A HASH RATHER THAN THE SHAPE ITSELF, because this value is printed: the leaf
    PATHS are field names and safe, but a shape printed in full invites the next
    reader to add the values beside it.
    """
    calls: list[dict[str, object]] = []
    for entry in _list(row, "calls"):
        if not isinstance(entry, dict):
            raise QuarantineError(f"{KIND}.calls: expected objects, found {entry!r}")
        written = entry.get("written")
        calls.append({
            "name": _text(entry, "name"),
            "leaves": sorted(str(one) for one in (written if isinstance(written, dict) else {})),
            "parsed": isinstance(entry.get("parsed"), dict),
            "refusal": f"{entry.get('refusal_path', '')}|{entry.get('refusal_rule', '')}"})
    shape = {"termination": _text(row, "termination"), "calls": calls,
             "records": len(_list(row, "state")), "answered": bool(_text(row, "reply").strip())}
    return hashlib.sha256(json.dumps(shape, ensure_ascii=False, sort_keys=True)
                          .encode("utf-8")).hexdigest()[:12]


def read_run(directory: Path) -> RunReading:
    """One run directory, reduced to `RunReading`.

    THE META FILE IS REQUIRED and its absence is a refusal. It is the only thing
    that says which corpus, which models and which tier the run was — and a run
    compared under unknown conditions is exactly the comparison this module
    exists to refuse. A run interrupted before it wrote one is answered with its
    name, not left out of the count in silence.

    ARMS EXCLUDED BY TERMINATION ARE NOT EVIDENCE (`EXCLUDED_TERMINATIONS`): a
    provider error is a fact about the provider, and an arm that died would
    otherwise read as an arm that behaved differently — the tool would then
    quarantine the cases that happened to be in flight during an outage.
    """
    metas = sorted(directory.glob("*.meta.json"))
    if not metas:
        raise QuarantineError(f"{directory}: нет *.meta.json — под какими моделями и по "
                              f"какому корпусу шёл прогон, сказать нечем")
    meta = json.loads(metas[0].read_text(encoding="utf-8"))
    behaviour: dict[tuple[str, str], set[str]] = {}
    labels: dict[str, tuple[str, str]] = {}
    for path in sorted(directory.glob("*.arms.jsonl")):
        for row in r.read_rows(path):
            arm = _text(row, "arm")
            if arm not in ARMS:
                raise QuarantineError(f"{path}: плечо {arm!r} не из {list(ARMS)}")
            if _text(row, "termination") in EXCLUDED_TERMINATIONS:
                continue
            case_id = _text(row, "case_id")
            labels[case_id] = (_text(row, "kind"), _text(row, "register"))
            behaviour.setdefault((case_id, arm), set()).add(behaviour_fingerprint(row))
    return RunReading(
        run_id=str(meta.get("run_id", metas[0].name.split(".")[0])), directory=directory,
        finished=str(meta.get("finished", "")),
        conditions=tuple((key, str(meta.get(key, ""))) for key in CONDITION_KEYS),
        behaviour={key: frozenset(values) for key, values in behaviour.items()}, labels=labels)


def run_dirs_from_registry(path: Path) -> tuple[Path, ...]:
    """The run directories `runs.json` names, in the order it names them.

    THE REGISTRY IS ANOTHER COMPONENT'S FILE (§1.2) and this reader takes one
    thing from it: where each run's files are. Everything else — the tier, the
    models, the digest — is read from the runs themselves, so a registry row
    that drifted from the directory it points at cannot make two runs look
    comparable when they are not.

    AN INTERRUPTED RUN IS SKIPPED, AND SAID OUT LOUD (second return value). The
    registry is required to keep the row of a run that spent money and stopped
    (§1.2), and such a run never wrote a `meta.json` — so `read_run` refuses it
    by design, and the whole command died on the first Ctrl-C in the history.
    Skipping is not silence about a condition: the registry already RECORDED the
    state, so this is reading the file rather than guessing. A directory named by
    hand is still refused — there nobody said the run was interrupted.
    """
    if not path.exists():
        raise QuarantineError(f"{path}: реестра прогонов нет; передайте каталоги прогонов "
                              f"аргументами")
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("runs") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise QuarantineError(f"{path}: ожидался список прогонов или "
                              f"{{\"runs\": [...]}}, найдено {type(rows).__name__}")
    directories: list[Path] = []
    skipped: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise QuarantineError(f"{path}[{index}]: ожидался объект, найдено {row!r}")
        named = [str(row[key]) for key in REGISTRY_DIR_KEYS if key in row]
        if not named:
            raise QuarantineError(f"{path}[{index}]: строка не называет каталог прогона "
                                  f"(искали {list(REGISTRY_DIR_KEYS)}), есть {sorted(row)}")
        if str(row.get("state", "")) in SKIPPED_STATES:
            skipped.append(str(row.get("run_id", named[0])))
            continue
        candidate = Path(named[0])
        directories.append(candidate if candidate.is_absolute() else path.parent / candidate)
    return tuple(directories), tuple(skipped)


# --- the question ----------------------------------------------------------------------

def _grouped(readings: Sequence[RunReading]) -> dict[tuple[tuple[str, str], ...],
                                                     list[RunReading]]:
    """Runs by the conditions they ran under, each group in the order they
    finished — «three consecutive runs» is a claim about one set of conditions,
    and a window that crossed a model change would measure the change."""
    groups: dict[tuple[tuple[str, str], ...], list[RunReading]] = {}
    for reading in readings:
        groups.setdefault(reading.conditions, []).append(reading)
    return {conditions: sorted(runs, key=lambda one: (one.finished, one.run_id))
            for conditions, runs in groups.items()}


def _flapped(window: Sequence[RunReading], case_id: str) -> tuple[tuple[str, int], ...] | None:
    """How many distinct behaviours each arm showed across this window, or None
    when the window cannot answer.

    IT CANNOT ANSWER unless every arm was observed in EVERY run of the window:
    an arm missing from one run is a case that was not attempted (excluded
    termination, a partial run, a tier that did not hold it), and reading an
    absence as a change would quarantine the cases an outage happened to catch.
    """
    per_arm: list[tuple[str, int]] = []
    for arm in ARMS:
        seen: set[str] = set()
        for reading in window:
            marks = reading.behaviour.get((case_id, arm))
            if not marks:
                return None
            seen |= marks
        per_arm.append((arm, len(seen)))
    return tuple(per_arm)


def unstable_cases(readings: Sequence[RunReading], window: int) -> tuple[Suspect, ...]:
    """Cases that flapped at EVERY arm across `window` consecutive runs of the
    same conditions.

    EVERY WINDOW IS SCANNED, not only the latest: a case that flapped in three
    runs and has been quiet since is still the case that made three family
    shares noisier, and the count of qualifying windows is what tells a reader
    whether it is history or the present. The window reported is the NEWEST one.
    """
    if window < 2:
        raise QuarantineError(f"окно {window}: сравнивать нестабильность можно от двух "
                              f"прогонов, ТЗ просит три")
    found: dict[str, Suspect] = {}
    for runs in _grouped(readings).values():
        for start in range(0, len(runs) - window + 1):
            slice_ = runs[start:start + window]
            shared = set.intersection(*[{case for case, _arm in one.behaviour} for one in slice_])
            for case_id in sorted(shared):
                per_arm = _flapped(slice_, case_id)
                if per_arm is None or any(count < 2 for _arm, count in per_arm):
                    continue
                previous = found.get(case_id)
                kind, register = slice_[-1].labels.get(case_id, ("", ""))
                found[case_id] = Suspect(
                    case_id=case_id, kind=kind, register=register,
                    runs=tuple(one.run_id for one in slice_), per_arm=per_arm,
                    windows=(previous.windows + 1) if previous else 1)
    return tuple(sorted(found.values(), key=lambda one: (-one.windows, one.case_id)))


def report(readings: Sequence[RunReading], window: int) -> list[str]:
    """What to print: the groups compared, the suspects, and the reason a group
    could not be asked at all — because «карантин: 0» reads as «nothing is
    wrong» whether the three runs agreed or there were never three of them."""
    lines: list[str] = []
    groups = _grouped(readings)
    for conditions, runs in sorted(groups.items()):
        label = " · ".join(f"{key}={value[:12] if key == 'digest' else value}"
                           for key, value in conditions)
        lines.append(f"условия: {label} · прогонов {len(runs)}"
                     + ("" if len(runs) >= window else f" — меньше {window}, сравнивать нечего"))
        for one in runs:
            lines.append(f"  {one.run_id[:8]} · {one.finished or 'дата неизвестна'} · "
                         f"случаев {len({case for case, _arm in one.behaviour})} · "
                         f"{one.directory}")
    if len(groups) > 1:
        lines.append(f"условия различались: {len(groups)} набора — окна не пересекают их, "
                     f"случай под другой моделью или другим корпусом не сравнивается")
    suspects = unstable_cases(readings, window)
    lines.append(f"карантин: {len(suspects)} случаев нестабильны у ВСЕХ плеч "
                 f"в {window} прогонах подряд")
    for suspect in suspects:
        arms = " / ".join(f"{arm} {count}" for arm, count in suspect.per_arm)
        lines.append(f"  {suspect.case_id} · {suspect.kind}/{suspect.register} · "
                     f"отпечатков: {arms} · окон {suspect.windows} · "
                     f"прогоны {', '.join(one[:8] for one in suspect.runs)}")
    if suspects:
        lines.append("пометка случая — решение человека: этот отчёт ничего не меняет "
                     "ни в корпусе, ни в прогонах")
    return lines


def main() -> int:
    """ОДНО НАПИСАНИЕ `main` НА ПАКЕТ: без параметров, argparse сам читает
    `sys.argv`. Этот модуль принимал `argv` — удобнее для теста и на одну
    сигнатуру больше для всех: единая дверь пакета (`python3 -m bench.agentpii5`)
    зовёт двенадцать команд, и та, что зовётся иначе, требует у диспетчера
    отдельной ветки, то есть места, где команду можно забыть."""
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="*", help="каталоги прогонов, от трёх")
    parser.add_argument("--runs-file", default="",
                        help="реестр прогонов (§1.2) вместо перечисления каталогов")
    parser.add_argument("--window", type=int, default=WINDOW,
                        help="сколько подряд идущих прогонов считать окном")
    args = parser.parse_args()

    directories = [Path(one) for one in args.runs]
    # ОТКАЗ — СТРОКОЙ, А НЕ TRACEBACK'ОМ. Всё, что ниже отказывается, отказывается
    # по названной причине (`QuarantineError`), и сырой стек вместо неё послал бы
    # читателя чинить этот модуль вместо своего реестра.
    try:
        if args.runs_file:
            from_registry, skipped = run_dirs_from_registry(Path(args.runs_file))
            directories.extend(from_registry)
            if skipped:
                print(f"пропущено прерванных прогонов: {len(skipped)} "
                      f"({', '.join(skipped)}) — у прерванного прогона нет meta.json, "
                      f"то есть условий, под которыми его можно сравнивать")
        if not directories:
            print("нечего читать: передайте каталоги прогонов или --runs-file",
                  file=sys.stderr)
            return 2
        readings = [read_run(one) for one in directories]
        lines = report(readings, args.window)
    except QuarantineError as refused:
        print(str(refused), file=sys.stderr)
        return 2
    for line in lines:
        print(line)
    # ZERO WHATEVER IS FOUND. A suspect is a question for a person, not a failed
    # check; a non-zero exit would put this report into a pipeline, and the next
    # step of that pipeline would be something deciding on its own which cases
    # leave the corpus — the one decision §7.2 keeps for the owner.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
