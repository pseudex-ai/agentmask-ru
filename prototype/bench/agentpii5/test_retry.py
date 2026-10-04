"""§1.4 extended: flaky provider failures are retried, counted, never duplicated.

    cd prototype && source .venv/bin/activate && python3 -m bench.agentpii5.test_retry

Self-contained: no model, no network, no bundle. A `TripleRunner` that raises
`ConnectorError` / `ConnectorLimit` / `WriterError` / a transport error and then
recovers drives the SAME `run_with_retries` + `drive_v5` the live run uses, so
the claim «a provider blip no longer excludes the triple forever» is proven on
the real loop and not on a test-only seam.

WHAT IS PROVEN HERE.
* `runinfo.is_transient_error` recognises the three live flaky classes AND
  transport, and refuses our deterministic defects (`ValueError`, `KeyError`,
  `FileNotFoundError`) — a retry of those is three waits before the same crash.
* `run_with_retries` re-runs the triple up to `policy.attempts` times, takes the
  first success, stamps the real attempt count into `triple["attempts"]`, and
  does NOT write anything for the discarded attempts.
* `drive_v5` turns an exhausted flaky triple into one `excluded` row carrying
  `attempts`, and the run continues — the same contract `--repeats` must not be
  confused with.
* The first backoff is `policy.base_s` (`--retry-delay`), not a hardcoded 2.
"""
import asyncio
import tempfile
from collections.abc import Callable
from pathlib import Path

from bench.agentpii4.writer import WriterError
from bench.agentpii5 import harness as h
from bench.agentpii5 import records as r
from bench.agentpii5 import runinfo
from bench.agentpii5.connectors import ConnectorError, ConnectorLimit
from bench.agentpii5.contracts import CaseV5
from bench.agentpii5.fixtures import NAME_ITEM, PHONE_ITEM, _case, _hop

RUN_ID: str = "retry1"
REAL_NAME: str = NAME_ITEM.value


def _fixture_case() -> CaseV5:
    hops = (_hop("IN", "user", "p1", 0, 0, "", -1, -1, ""),
            _hop("OUT", "answer", "p1", 1, 0, "", -1, -1, ""))
    return _case("c-0001", "single", (f"{REAL_NAME}, {PHONE_ITEM.value}",),
                 (NAME_ITEM, PHONE_ITEM), hops)


async def _no_pause(seconds: float) -> None:
    """Отступ без ожидания: кривую отступа проверяет `test_runinfo`."""
    return None


def _policy(attempts: int, base_s: float,
            pause: Callable[[float], object] = _no_pause) -> h.DrivePolicy:
    return h.DrivePolicy(attempts=attempts, base_s=base_s, pause=pause,
                         jitter=lambda: 1.0, expected_per_case_usd=0.0)


def _triple(case_id: str, status: str = "complete") -> h.TripleResult:
    """Минимальная успешная тройка: `run_with_retries` трогает только `triple`,
    `drive_v5` пишет `triple` и читает `cost_usd`/`judge`/`status`."""
    triple = {"case_id": case_id, "repeat": 0, "kind": "single",
              "behaviour": "single", "register": "clean", "cluster": "c1",
              "cap_usd": 1.0, "cost_usd": 0.01,
              **r.triple_totals_to_json(h.triple_totals(None, 0)),
              "status": status, "reason": "", "attempts": 1, "arms": {}, "judge": {}}
    return h.TripleResult([], None, (), None, triple)


# --- the transient classification --------------------------------------------------------------

def test_transient_classes_are_recognized() -> list[str]:
    """Три класса живых флаков И транспорт — флаки; наши детерминированные
    дефекты — нет."""
    failures: list[str] = []
    flaky = (ConnectorError("DeepSeek response ended incomplete"),
             ConnectorLimit("tool call limit reached"),
             WriterError("slot 'p1' does not round-trip as a JSON string"),
             ConnectionError("сброс"))
    for error in flaky:
        if not runinfo.is_transient_error(error):
            failures.append(f"{type(error).__name__} не признан флаки — тройку снимут навсегда")
    # WriterError — подкласс ValueError, и именно поэтому «ValueError маскирования»
    # НЕ должен слиться с ним: повтор детерминированного parity-бага — три
    # ожидания перед тем же отказом.
    for ours in (ValueError("маскирование разошлось"), KeyError("p1"),
                 FileNotFoundError("нет файла")):
        if runinfo.is_transient_error(ours):
            failures.append(f"{type(ours).__name__} признан флаки — детерминированный дефект повторят")
    return failures


# --- the retry loop ----------------------------------------------------------------------------

def test_retry_takes_the_first_success_and_records_attempts() -> list[str]:
    """Два флаки подряд — третья попытка доезжает, и `attempts` называется честно."""
    failures: list[str] = []
    tries: list[int] = []

    async def flaky(case: CaseV5, repeat: int) -> h.TripleResult:
        tries.append(1)
        if len(tries) < 3:
            raise ConnectorError("DeepSeek response ended incomplete")
        return _triple(case.base.id)

    case = _fixture_case()
    result = asyncio.run(h.run_with_retries(flaky, case, 0, _policy(3, 2.0)))
    if len(tries) != 3:
        failures.append(f"попыток {len(tries)}, ожидались 3 (два флаки, третий успех)")
    if result.triple.get("attempts") != 3:
        failures.append(f"attempts = {result.triple.get('attempts')!r}, ожидались 3")
    return failures


def test_a_flaky_that_never_recovers_stays_excluded_with_attempts() -> list[str]:
    """Все N попыток флаки — тройка СНИМАЕТСЯ одной строкой, прогон идёт дальше,
    `attempts` лежит в строке. Ни одна из брошенных попыток не пишет строку."""
    failures: list[str] = []
    tries: list[int] = []

    async def always(case: CaseV5, repeat: int) -> h.TripleResult:
        tries.append(1)
        raise ConnectorLimit("tool call limit reached")

    case = _fixture_case()
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "v5"
        run_dir.mkdir()
        result = asyncio.run(h.drive_v5([case], 1, always, run_dir, RUN_ID, 1,
                                        frozenset(), _policy(3, 2.0)))
        if len(tries) != 3:
            failures.append(f"попыток {len(tries)}, ожидались 3")
        if result.transport_terminated != 1:
            failures.append(f"снятых флаки {result.transport_terminated}, ожидался один")
        rows = r.read_rows(r.run_file(run_dir, RUN_ID, "<run>.triples.jsonl"))
        if len(rows) != 1:
            failures.append(f"строк троек {len(rows)}, ожидалась одна — повтор не должен плодить строки")
        row = rows[0]
        if str(row.get("status")) != "excluded":
            failures.append(f"исчерпанная флаки тройка записана {row.get('status')!r}, не excluded")
        if runinfo.TRANSPORT_TERMINATED not in str(row.get("reason")):
            failures.append(f"причина не называет флаки: {row.get('reason')!r}")
        if row.get("attempts") != 3:
            failures.append(f"attempts = {row.get('attempts')!r}, ожидались 3")
    return failures


def test_the_successful_triple_is_written_once_with_attempts() -> list[str]:
    """Полный путь `drive_v5`: флаки, потом успех — пишется ОДНА строка тройки,
    и `attempts` в ней равен числу сделанных попыток (не 1, не N строк)."""
    failures: list[str] = []
    tries: list[int] = []

    async def flaky(case: CaseV5, repeat: int) -> h.TripleResult:
        tries.append(1)
        if len(tries) < 2:
            raise WriterError("slot 'p1' does not round-trip as a JSON string")
        return _triple(case.base.id)

    case = _fixture_case()
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp) / "v5"
        run_dir.mkdir()
        result = asyncio.run(h.drive_v5([case], 1, flaky, run_dir, RUN_ID, 1,
                                        frozenset(), _policy(2, 2.0)))
        if result.transport_terminated != 0:
            failures.append(f"успешная тройка помечена снятой: {result.transport_terminated}")
        rows = r.read_rows(r.run_file(run_dir, RUN_ID, "<run>.triples.jsonl"))
        if len(rows) != 1:
            failures.append(f"строк троек {len(rows)}, ожидалась одна (брошенная попытка не пишет)")
        if rows[0].get("attempts") != 2:
            failures.append(f"attempts = {rows[0].get('attempts')!r}, ожидались 2")
        if str(rows[0].get("status")) != "complete":
            failures.append(f"успешная тройка записана {rows[0].get('status')!r}")
    return failures


def test_the_first_backoff_is_the_configured_delay() -> list[str]:
    """`--retry-delay` доезжает до первого отступа: `policy.base_s`, не константа."""
    failures: list[str] = []
    waits: list[float] = []

    async def pause(seconds: float) -> None:
        waits.append(seconds)

    async def always(case: CaseV5, repeat: int) -> h.TripleResult:
        raise ConnectionError("сброс")

    case = _fixture_case()
    policy = h.DrivePolicy(attempts=3, base_s=5.0, pause=pause, jitter=lambda: 1.0,
                           expected_per_case_usd=0.0)
    try:
        asyncio.run(h.run_with_retries(always, case, 0, policy))
        failures.append("исчерпанный флаки не поднял TransportExhausted")
    except h.TransportExhausted:
        pass
    if len(waits) != 2:
        failures.append(f"пауз {len(waits)}, ожидались две (между тремя попытками)")
    elif waits[0] != runinfo.backoff_seconds(1, 1.0, 5.0):
        failures.append(f"первый отступ {waits[0]}, ожидался {runinfo.backoff_seconds(1, 1.0, 5.0)} — "
                        f"base_s не доехал до backoff")
    return failures


def main() -> int:
    checks: tuple[tuple[str, Callable[[], list[str]]], ...] = (
        ("transient_classes_are_recognized", test_transient_classes_are_recognized),
        ("retry_takes_the_first_success_and_records_attempts",
         test_retry_takes_the_first_success_and_records_attempts),
        ("a_flaky_that_never_recovers_stays_excluded_with_attempts",
         test_a_flaky_that_never_recovers_stays_excluded_with_attempts),
        ("the_successful_triple_is_written_once_with_attempts",
         test_the_successful_triple_is_written_once_with_attempts),
        ("the_first_backoff_is_the_configured_delay", test_the_first_backoff_is_the_configured_delay),
    )
    failures: list[str] = []
    for name, check in checks:
        problems = check()
        print(f"  {name}: {'PASS' if not problems else 'FAIL'}")
        failures += [f"{name}: {one}" for one in problems]
    print("retry: PASS" if not failures else "retry: FAIL\n  " + "\n  ".join(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
