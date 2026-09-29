"""`--timeout-scale`: the per-case deadline is multiplied at EVERY v5 call site.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_timeout_scale

Self-contained: no model, no network, no bundle. v5 wraps v4's `_timeout` in
three places — `converse(... timeout_s=...)`, `asyncio.wait_for(drive(),
timeout=...)` and the `timeout` arm's reason — and a scale that reached only two
of them would leave a run whose record and its actual deadline disagree about
how long the model had. Each is pinned here over the real seams, so a later edit
that hardcodes one of the three back to v4's `_timeout` goes red.
"""
import asyncio
from collections.abc import Callable
from pathlib import Path

from bench.agentpii4 import harness as v4_harness
from bench.agentpii5 import harness as h
from bench.agentpii5.connectors import Conversation, DialogueHooks, ToolSpec, Usage
from bench.agentpii5.mock import seed_backend_v5

RUN_ID: str = "tscale1"
SCALE: float = 2.0


class RecordingTimeoutAgent:
    """A connector double that records the `timeout_s` `_run` handed it."""

    def __init__(self) -> None:
        self.timeout_s: float | None = None

    async def converse(self, system: str, tools: tuple[ToolSpec, ...],
                       user_indices: tuple[int, ...], hooks: DialogueHooks,
                       timeout_s: float, max_calls: int) -> Conversation:
        self.timeout_s = timeout_s
        return Conversation((), Usage(1, 0, 1, 0, 0.0, "fixture"), 0, "fixture-session", 1)


def _case() -> h.CaseV5:
    cases, _ = h._load_corpus(Path(__file__).with_name("corpus.v5.json"))
    return next(case for case in cases if case.base.id == "validate-000")


def test_scaled_timeout_is_v4_times_scale() -> list[str]:
    """The wrapper multiplies, and scale=1.0 is v4's value unchanged."""
    failures: list[str] = []
    base = _case().base
    v4 = v4_harness._timeout(base)
    if v4 <= 0:
        failures.append("v4's _timeout не положителен — проверять множитель не на чем")
    if h.scaled_timeout(base, 1.0) != v4:
        failures.append(f"scale=1.0 дал {h.scaled_timeout(base, 1.0)}, ожидался v4's {v4}")
    if h.scaled_timeout(base, SCALE) != SCALE * v4:
        failures.append(f"scale={SCALE} дал {h.scaled_timeout(base, SCALE)}, "
                        f"ожидалось {SCALE}×{v4}")
    return failures


def test_connected_arms_hands_the_scaled_timeout_to_converse() -> list[str]:
    """`ConnectedArms._run` → `converse(timeout_s=…)` gets the scaled value, and
    the default connector is not scaled by accident."""
    failures: list[str] = []
    case = _case()
    agent = RecordingTimeoutAgent()
    asyncio.run(h.ConnectedArms(agent, timeout_scale=SCALE).control(
        case, "C", 0, seed_backend_v5(case), "fixture", 0.15, RUN_ID))
    expected = h.scaled_timeout(case.base, SCALE)
    if agent.timeout_s != expected:
        failures.append(f"converse получил {agent.timeout_s}, ожидался {expected}")

    plain = RecordingTimeoutAgent()
    asyncio.run(h.ConnectedArms(plain).control(
        case, "C", 0, seed_backend_v5(case), "fixture", 0.15, RUN_ID))
    if plain.timeout_s != v4_harness._timeout(case.base):
        failures.append(f"scale по умолчанию дал {plain.timeout_s}, ожидался v4's "
                        f"{v4_harness._timeout(case.base)}")
    return failures


def test_arm_verdict_names_the_scaled_deadline() -> list[str]:
    """The `timeout` arm's reason carries the SAME scaled value the deadline used."""
    failures: list[str] = []
    base = _case().base
    outcome = h.arm_verdict(base, "I", 0, asyncio.TimeoutError(), 0.5, RUN_ID, SCALE)
    expected = f"таймаут {h.scaled_timeout(base, SCALE):.0f}s"
    if outcome.run.termination != "timeout":
        failures.append(f"дедлайн дал {outcome.run.termination!r}, не timeout")
    if outcome.meta.reason != expected:
        failures.append(f"причина {outcome.meta.reason!r}, ожидалась {expected!r}")
    return failures


def test_the_guarded_claude_arm_threads_the_same_scale_to_both_uses() -> list[str]:
    """`_guarded_arm_v5` hands ONE scale to `run_arm_v5` (the `wait_for` deadline)
    and to `arm_verdict` (the reason), so the two cannot disagree."""
    failures: list[str] = []
    case = _case()
    seen: list[float] = []

    async def fake_run_arm_v5(case: h.CaseV5, arm: str, repeat: int, gateway: object,
                              backend: object, model: str, cap: float, run_id: str,
                              timeout_scale: float = 1.0) -> h.ArmOutcomeV5:
        seen.append(timeout_scale)
        raise asyncio.TimeoutError()

    original = h.run_arm_v5
    h.run_arm_v5 = fake_run_arm_v5  # type: ignore[assignment]
    try:
        result = asyncio.run(h._guarded_arm_v5(case, 0, None, None, "m", 0.5, RUN_ID, SCALE))
    finally:
        h.run_arm_v5 = original
    if seen != [SCALE]:
        failures.append(f"run_arm_v5 получил scale {seen}, ожидался [{SCALE}]")
    if result.base.run.termination != "timeout":
        failures.append(f"вердикт {result.base.run.termination!r}, не timeout")
    expected = f"таймаут {h.scaled_timeout(case.base, SCALE):.0f}s"
    if result.base.meta.reason != expected:
        failures.append(f"причина {result.base.meta.reason!r}, ожидалась {expected!r}")
    return failures


def test_drive_policy_carries_the_scale() -> list[str]:
    """`DrivePolicy.timeout_scale` holds the run-level knob, defaulting to 1.0."""
    failures: list[str] = []
    policy = h.DrivePolicy(attempts=1, base_s=1.0, pause=asyncio.sleep, jitter=lambda: 1.0,
                           expected_per_case_usd=0.0, timeout_scale=SCALE)
    if policy.timeout_scale != SCALE:
        failures.append(f"DrivePolicy.timeout_scale = {policy.timeout_scale}, "
                        f"ожидался {SCALE}")
    default = h.DrivePolicy(attempts=1, base_s=1.0, pause=asyncio.sleep, jitter=lambda: 1.0,
                            expected_per_case_usd=0.0)
    if default.timeout_scale != 1.0:
        failures.append(f"DrivePolicy.timeout_scale по умолчанию = {default.timeout_scale}, "
                        f"ожидался 1.0")
    return failures


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("scaled_timeout_is_v4_times_scale", test_scaled_timeout_is_v4_times_scale),
        ("connected_arms_hands_the_scaled_timeout_to_converse",
         test_connected_arms_hands_the_scaled_timeout_to_converse),
        ("arm_verdict_names_the_scaled_deadline", test_arm_verdict_names_the_scaled_deadline),
        ("the_guarded_claude_arm_threads_the_same_scale_to_both_uses",
         test_the_guarded_claude_arm_threads_the_same_scale_to_both_uses),
        ("drive_policy_carries_the_scale", test_drive_policy_carries_the_scale),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("timeout_scale: PASS" if not failures else "timeout_scale: FAIL\n  "
          + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
