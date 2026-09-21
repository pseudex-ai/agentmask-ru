"""The gates must be able to go red.

A check that cannot fail is not a check, and a benchmark's own checks are
the last place to find that out from a customer. Each test here breaks one
property on purpose and requires the gate to notice.
"""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from agentmask_ru.gates import run_gates
from agentmask_ru.schema import Case, PiiItem, load_dir

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "cases"


def _verdicts(cases: list[Case]) -> dict[str, bool]:
    return {result.name: result.ok for result in run_gates(ROOT, cases)}


def test_the_corpus_as_committed_passes_every_gate() -> None:
    assert all(_verdicts(load_dir(CASES)).values())


def test_a_drifted_offset_is_caught() -> None:
    cases = load_dir(CASES)
    broken = cases[0]
    item = broken.pii[0]
    cases[0] = replace(broken, pii=(replace(item, start=item.start + 1),) + broken.pii[1:])
    assert not _verdicts(cases)["G2-G5 структура случая"]


def test_a_case_without_negatives_is_caught() -> None:
    cases = load_dir(CASES)
    cases[0] = replace(cases[0], negatives=())
    assert not _verdicts(cases)["G2-G5 структура случая"]


def test_an_unreachable_canonical_is_caught_by_the_passthrough() -> None:
    # A canonical form that differs from what the message says cannot be
    # delivered by ANY masker — including one that changes nothing. The
    # gate must blame the case, which is what G6 exists to do.
    cases = load_dir(CASES)
    target = next(c for c in cases if any(p.tool_param for p in c.pii))
    index = cases.index(target)
    item = next(p for p in target.pii if p.tool_param)
    others = tuple(p for p in target.pii if p is not item)
    cases[index] = replace(target, pii=(replace(item, canonical=item.canonical + "-ерунда"),) + others)
    assert not _verdicts(cases)["G6 passthrough проходит корпус"]


def test_a_case_the_naive_masker_cannot_touch_must_say_why() -> None:
    cases = load_dir(CASES)
    hidden = next(c for c in cases if c.hard is not None)
    cases[cases.index(hidden)] = replace(hidden, hard=None)
    assert not _verdicts(cases)["G7 эталонный маскер отличим от passthrough"]


def test_an_emptied_stratum_is_caught() -> None:
    # Every name drawn from the frequency head: the corpus can no longer
    # fail a system with a large gazetteer, and G8 must say so.
    cases = load_dir(CASES)
    flattened: list[Case] = []
    for case in cases:
        items = tuple(replace(p, tier="common") if p.type == "NAME" else p for p in case.pii)
        flattened.append(replace(case, pii=items))
    assert not _verdicts(flattened)["G8 страты наполнены"]


def test_a_private_import_is_caught(tmp_path: Path) -> None:
    src = tmp_path / "src" / "agentmask_ru"
    src.mkdir(parents=True)
    (src / "leaky.py").write_text("from pseudex.vault import Vault\n", encoding="utf-8")
    (tmp_path / "results").mkdir()
    verdicts = {result.name: result.ok for result in run_gates(tmp_path, load_dir(CASES))}
    assert not verdicts["G10 нет импортов из закрытого движка"]


def test_a_result_from_another_corpus_is_marked_stale(tmp_path: Path) -> None:
    import json

    (tmp_path / "src").mkdir()
    results = tmp_path / "results" / "somebody"
    results.mkdir(parents=True)
    (results / "run.json").write_text(json.dumps({"manifest": {"corpus_digest": "deadbeefdeadbeef"}}), encoding="utf-8")
    verdicts = {result.name: result.ok for result in run_gates(tmp_path, load_dir(CASES))}
    assert not verdicts["G11 результаты считаны на текущем корпусе"]
