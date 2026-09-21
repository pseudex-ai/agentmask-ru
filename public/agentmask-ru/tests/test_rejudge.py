"""A stored run is read by the current judge, and only the verdicts move."""

from pathlib import Path

from agentmask_ru.adapters.reference import NoopMasker
from agentmask_ru.harness import run as run_harness
from agentmask_ru.results import manifest, observations_of, rejudge, rescored, to_payload
from agentmask_ru.schema import load_dir
from agentmask_ru.score import score

_ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict[str, object]:
    # Generated in-memory, not read from `results/`: results are .gitignored
    # (numbers are article-only), so the test carries its own run — the no-op
    # masker over the first twelve cases, one verdict per item.
    cases = load_dir(_ROOT / "cases")[:12]
    observations = run_harness(NoopMasker(), cases, "copier", 20260920)
    meta = manifest("noop", {}, "copier", 20260920, cases, "test", "")
    return to_payload(meta, score(observations), observations)


def test_observations_round_trip_through_the_dataclasses() -> None:
    payload = _payload()
    observations = observations_of(payload)
    assert len(observations) == len(payload["observations"])  # type: ignore[arg-type]


def test_rejudge_keeps_the_record_and_recomputes_only_verdicts() -> None:
    cases = load_dir(_ROOT / "cases")
    observations = observations_of(_payload())
    before = [(i.substitute, i.delivered, i.altered) for o in observations for i in o.items]
    rejudge(observations, cases)
    after = [(i.substitute, i.delivered, i.altered) for o in observations for i in o.items]
    assert before == after


def test_rescored_payload_carries_the_repaired_line() -> None:
    cases = load_dir(_ROOT / "cases")
    fresh = rescored(_payload(), cases)
    assert "round_trip_repaired" in fresh["lines"]  # type: ignore[operator]
    assert fresh["rescored"] == {"benchmark_version": fresh["manifest"]["benchmark_version"]}  # type: ignore[index]
