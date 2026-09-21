"""A stored run is read by the current judge, and only the verdicts move."""

from pathlib import Path

from agentmask_ru.results import observations_of, rejudge, rescored
from agentmask_ru.schema import load_dir

_ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict[str, object]:
    # The smallest real run file: the no-op masker, one verdict per item.
    import json

    runs = sorted((_ROOT / "results" / "noop").glob("*.json"))
    return json.loads(runs[-1].read_text(encoding="utf-8"))


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
