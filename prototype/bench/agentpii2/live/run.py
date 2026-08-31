"""The live transparency axis: every case twice, once plain and once masked.

    python3 bench/agentpii2/live/run.py --tier nano --ceiling 2.00
    python3 bench/agentpii2/live/run.py --ids transfer-...-00,cmp0000-same-place-clean
    python3 bench/agentpii2/live/run.py --tier small --self-control --out live/runs/

WHAT THIS MEASURES AND WHAT THE OFFLINE SCORER CANNOT. `score.py` assumes a
PERFECT model — one that copies what it was handed — which is what isolates the
gateway's contribution on the seven offline axes. The eighth axis is the one that
assumption destroys: whether a real model, reading substitutes instead of people,
still chooses the same tool with the same arguments. It costs money per case, so
everything here is built around a ceiling that is reserved before the call and
reconciled against what was actually billed.

THREE ARMS, AND THE THIRD IS NOT OPTIONAL FOR AN HONEST NUMBER. Arm A is plain
text, arm B goes through the gateway. `--self-control` adds arm A′ — plain text
again, a second draw from the same model — and scores A against A′ through the
same comparator. Without it, «transparency 80%» is indistinguishable from a model
that agrees with itself 80% of the time, and the reader has no way to know which.

A CASE THAT CANNOT RESERVE IS RECORDED INCOMPLETE. Never dropped, never imputed.
A run that quietly sheds what it cannot afford reports the cases that were cheap,
and the cheap cases are the short clean ones — the population whose numbers are
already good.

NO MESSAGE TEXT IS WRITTEN TO THE RESULT FILE unless `--dump-text` says so, and
never for a case whose text is hydrated from a licensed source. The `speech`
family comes from OpenSTT under CC BY-NC 4.0: measuring with it is allowed,
shipping it is not, and a results file committed to a repository is shipping.
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
import uuid
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from bench.agentpii2 import build  # noqa: E402
from bench.agentpii2.live import sample  # noqa: E402
from bench.agentpii2.live.agent import (  # noqa: E402
    ArmResult, ObservedCall, run_arm, strip_prefix, user_turns,
)
from bench.agentpii2.live.budget import Budget  # noqa: E402
from bench.agentpii2.live.compare import (  # noqa: E402
    Divergence, compare_calls, control_matches,
)
from bench.agentpii2.live.gateway import LiveGateway  # noqa: E402
from bench.agentpii2.schema import Case, case_characters  # noqa: E402
from bench.agentpii2.score import _MemoDetector  # noqa: E402
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.vault import Vault  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

# The hard per-arm cap the SDK enforces, by how much text the case carries. Not
# one number: a `long` case is ~16 000 characters and a `short` one is under 400,
# so a single cap either strangles the long ones or reserves twenty times what a
# short one can spend and lets a ceiling admit a quarter of the cases it could.
#
# THE NUMBERS ARE ANCHORED TO A MEASUREMENT, not to a feeling: one short
# single-turn arm against `claude-sonnet-4-6` billed $0.0134 (probe, 30.08.2026),
# so `short` is about six times the observed cost. A cap that sits close to the
# mean is not conservative — it TRUNCATES the multi-turn cases, and a truncated
# trajectory scored as a finished one is worse than a case that did not run. A
# cap that sits far above it starves the ceiling instead, because a reservation
# is held at full value for the whole run. Six times is where those two costs
# crossed on the corpus's own turn counts.
CAPS: dict[str, float] = {"short": 0.10, "medium": 0.35, "long": 0.90}

MODEL = "claude-sonnet-4-6"


def _cap(case: Case) -> float:
    return CAPS.get(case.length_rung, CAPS["short"])


def _timeout(case: Case, base: float) -> float:
    """Per-arm wall clock, scaled by how many times the harness speaks. A flat
    timeout that fits a one-turn case kills a sixty-one-turn one at turn twelve
    and records it as a gateway problem."""
    return base + 25.0 * user_turns(case)


async def _one_case(case: Case, lead: Case | None, detector: _MemoDetector,
                    budget: Budget, model: str, run_id: str, timeout_s: float,
                    self_control: bool) -> dict[str, object]:
    """Run one case's arms, or record why it did not run.

    The reservation covers EVERY arm before the first one starts. Reserving per
    arm would admit a case, spend on arm A, then fail to afford arm B — and half
    a case is not a cheaper measurement, it is no measurement with a bill.
    """
    arms = 3 if self_control else 2
    cap = _cap(case)
    record: dict[str, object] = {
        "id": case.id, "family": case.family, "register": case.register,
        "difficulty": case.difficulty, "length_rung": case.length_rung,
        "relation": case.relation, "characters": case_characters(case),
        "cap_usd": round(cap * arms, 6), "arms": [], "cost_usd": 0.0,
    }
    if not await budget.reserve(cap * arms):
        record["status"] = "incomplete"
        record["reason"] = (f"потолок: нужно {cap * arms:.2f}, свободно "
                            f"{budget.ceiling - budget.held():.2f}")
        return record

    spent = 0.0
    started = time.monotonic()
    arm_records: list[dict[str, object]] = []
    record["arms"] = arm_records

    def account(arm: ArmResult) -> ArmResult:
        """Record and charge an arm the moment it returns, before anything that
        could raise. An arm whose cost is only booked at the end of a successful
        case is an arm whose bill disappears exactly when the case fails."""
        nonlocal spent
        arm_records.append(_arm_record(arm))
        spent += arm.cost_usd
        if arm.is_error or arm.subtype != "success":
            # FAIL CLOSED. A run stopped by `max_budget_usd` or an API error has
            # a PARTIAL trajectory, and a partial trajectory compared against a
            # complete one reports a divergence the gateway did not cause. The
            # repo's own rule — never fall back to a degraded result — applies to
            # a benchmark exactly as it applies to masking.
            raise RuntimeError(f"плечо {arm.arm} оборвалось: {arm.subtype}"
                               f"{' ' + str(arm.errors) if arm.errors else ''}")
        return arm

    try:
        plain = account(await run_arm(case, "plain", model, cap, run_id, None,
                                      _timeout(case, timeout_s)))

        vault = Vault(":memory:", "bench-live")
        audit = AuditLog(":memory:")
        gateway = LiveGateway(case, detector, vault, audit, MaskCache(512))
        if lead is not None:
            gateway.prime(lead)
        masked = account(await run_arm(case, "masked", model, cap, run_id, gateway,
                                       _timeout(case, timeout_s)))

        restored: list[dict[str, object]] = []
        residual: list[str] = []
        for call in masked.calls:
            values, leftover = gateway.restore(call.arguments)
            restored.append(values)
            residual.extend(leftover)

        verdict = compare_calls(case, plain, masked, restored, residual)
        verdict.control_matches_corpus = control_matches(case, plain)

        record["status"] = "complete"
        record["conversation_id"] = gateway.conversation_id
        record["plain_calls"] = [
            {"name": strip_prefix(call.name), "arguments": dict(call.arguments)}
            for call in plain.calls]
        record["masked_calls"] = [
            {"name": strip_prefix(call.name), "arguments": values}
            for call, values in zip(masked.calls, restored)]
        record["masked_calls_as_model_wrote"] = [
            {"name": strip_prefix(call.name), "arguments": dict(call.arguments)}
            for call in masked.calls]
        record["verdict"] = {
            "transparent": verdict.transparent,
            "transparent_on_pii": verdict.transparent_on_pii,
            "tools_same": verdict.tools_same,
            "arguments_same": verdict.arguments_same,
            "pii_arguments_same": verdict.pii_arguments_same,
            "answer_same": verdict.answer_same,
            "residual": verdict.residual,
            "plain_called": verdict.plain_called,
            "masked_called": verdict.masked_called,
            "control_matches_corpus": verdict.control_matches_corpus,
            "divergences": [asdict(one) for one in verdict.divergences],
        }
        if self_control:
            # The control arm gets its OWN failure boundary. It measures a floor
            # under the A/B number; losing it costs a floor, and throwing away a
            # completed A/B measurement because the third arm timed out would
            # cost the measurement the run exists for.
            try:
                twin = account(await run_arm(case, "plain2", model, cap, run_id,
                                             None, _timeout(case, timeout_s)))
                control = compare_calls(case, plain, twin,
                                        [dict(one.arguments) for one in twin.calls], [])
                record["self_control"] = {
                    "transparent": control.transparent,
                    "transparent_on_pii": control.transparent_on_pii,
                    "divergences": [asdict(one) for one in control.divergences],
                }
            except (asyncio.TimeoutError, RuntimeError, OSError, ValueError) as error:
                record["self_control_failed"] = f"{type(error).__name__}: {error}"
    except asyncio.TimeoutError:
        record["status"] = "incomplete"
        record["reason"] = f"таймаут {_timeout(case, timeout_s):.0f}s"
        # A timed-out run produced no ResultMessage and therefore no measured
        # cost. The reservation is charged IN FULL rather than at zero: the run
        # did happen and did bill, and a ledger that books it at zero would let
        # the next case spend money that is already gone.
        spent = max(spent, cap * arms)
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as error:
        record["status"] = "incomplete"
        record["reason"] = f"{type(error).__name__}: {error}"
    finally:
        record["cost_usd"] = round(spent, 6)
        record["wall_s"] = round(time.monotonic() - started, 2)
        await budget.settle(case.id, cap * arms, spent)
    return _scrub(record) if _licensed(case) else record


def _licensed(case: Case) -> bool:
    """True when this case's text is hydrated from a source we may measure with
    and may not ship. `speech` comes from OpenSTT `asr_calls_2_val` under
    CC BY-NC 4.0, and a result file is shipping: the values in a tool argument
    ARE the transcript, one phrase at a time."""
    return any(isinstance(message.get("source"), dict) for message in case.messages)


def _scrub(record: dict[str, object]) -> dict[str, object]:
    """Strip every value carried out of a licensed case, keeping the shape.

    The verdict is computed BEFORE this runs and is unaffected — what is lost is
    only a reader's ability to eyeball the strings, and for those seventeen cases
    that is the price of the licence.
    """
    for key in ("plain_calls", "masked_calls", "masked_calls_as_model_wrote"):
        for call in record.get(key) or []:
            call["arguments"] = {name: "<лицензионный источник>"
                                 for name in call["arguments"]}
    for holder in (record.get("verdict"), record.get("self_control")):
        for divergence in (holder or {}).get("divergences", []):
            divergence["plain"] = "<лицензионный источник>"
            divergence["masked"] = "<лицензионный источник>"
    return record


def _arm_record(arm: ArmResult) -> dict[str, object]:
    return {
        "arm": arm.arm, "cost_usd": round(arm.cost_usd, 6), "model": arm.model,
        "turns": arm.turns, "duration_ms": arm.duration_ms,
        "is_error": arm.is_error, "subtype": arm.subtype,
        "api_error_status": arm.api_error_status, "errors": list(arm.errors),
        "session_id": arm.session_id, "calls": len(arm.calls),
        "model_usage": {name: round(float(row.get("costUSD", 0.0)), 6)
                        for name, row in arm.model_usage.items()
                        if isinstance(row, dict)},
    }


async def _drive(cases: list[Case], leads: dict[str, Case], detector: _MemoDetector,
                 budget: Budget, model: str, run_id: str, timeout_s: float,
                 self_control: bool, concurrency: int) -> list[dict[str, object]]:
    limiter = asyncio.Semaphore(max(1, concurrency))
    records: list[dict[str, object] | None] = [None] * len(cases)

    # EXECUTION ORDER IS MOST-EXPENSIVE-FIRST, and it is a correctness choice
    # rather than a scheduling nicety. A reservation is held at its full cap for
    # the life of a case, so running the cheap cases first spends the ledger down
    # and then refuses the one case whose cap is large — at nano the `long` rung
    # reserves 1.80 of a 2.00 ceiling, so in draw order it is admitted never.
    # «The run sheds the expensive cases and reports the cheap ones» is precisely
    # the failure the incomplete-not-dropped rule exists to prevent, and an
    # ordering that makes it certain would have made that rule decorative. The
    # DRAW order is what the result file records; this only decides who goes
    # first.
    schedule = sorted(range(len(cases)), key=lambda index: -_cap(cases[index]))

    async def worker(index: int, case: Case) -> None:
        async with limiter:
            records[index] = await _one_case(
                case, leads.get(case.id), detector, budget, model, run_id,
                timeout_s, self_control)
            done = sum(1 for one in records if one is not None)
            row = records[index] or {}
            print(f"  [{done}/{len(cases)}] {case.id} {row.get('status')} "
                  f"${float(row.get('cost_usd') or 0.0):.4f} "
                  f"{'прозрачно' if (row.get('verdict') or {}).get('transparent') else ''}",
                  flush=True)

    await asyncio.gather(*(worker(index, cases[index]) for index in schedule))
    return [one for one in records if one is not None]


# --- re-judging a finished run, with no model and no money ------------------

def _rescore(payload: dict[str, object], everything: list[Case]) -> dict[str, object]:
    """Recompute the verdicts from a saved run.

    THE RUN FILE IS THE ARTEFACT, and the comparator is the part that changes.
    Every argument both arms produced is in there, so a new rule — the
    PII-argument number was one — can be applied to a run that has already been
    paid for. Re-running instead would spend the money again AND draw fresh
    samples from a nondeterministic model, so the two numbers would differ for
    two reasons at once and nobody could say which.

    THREE THINGS ARE CARRIED FORWARD RATHER THAN RECOMPUTED, because the run file
    does not carry what they need:

      * `answer_same` needs the assistant's prose, which is deliberately not
        stored — it is customer text and a run file is an artefact on a disk.
      * `residual` needs the vault, which was in memory and is gone.
      * `self_control` needs the third arm's calls, which are counted and not
        stored.

    A case whose values were scrubbed under licence keeps its stored verdict
    whole: re-judging «<лицензионный источник>» against itself would score every
    such case transparent by construction.
    """
    by_id = {case.id: case for case in everything}
    for record in payload["cases"]:  # type: ignore[union-attr]
        if record.get("status") != "complete" or record["id"] not in by_id:
            continue
        case = by_id[str(record["id"])]
        if _licensed(case):
            continue
        stored = record["verdict"]
        plain = _replay_arm("plain", record["plain_calls"])
        masked = _replay_arm("masked", record["masked_calls_as_model_wrote"])
        restored = [dict(call["arguments"]) for call in record["masked_calls"]]
        verdict = compare_calls(case, plain, masked, restored,
                                list(stored.get("residual") or []))
        verdict.answer_same = stored.get("answer_same")
        verdict.control_matches_corpus = stored.get("control_matches_corpus")
        if verdict.answer_same is False:
            # The row is carried with the flag. Carrying only the flag left the
            # rescored report one divergence short of the live one it re-judges,
            # and two reports of one run disagreeing on how many things went
            # wrong is the quiet kind of wrong that survives review.
            verdict.divergences.extend(
                Divergence(**one) for one in stored.get("divergences") or []
                if one.get("kind") == "answer")
        record["verdict"] = {
            "transparent": verdict.transparent,
            "transparent_on_pii": verdict.transparent_on_pii,
            "tools_same": verdict.tools_same,
            "arguments_same": verdict.arguments_same,
            "pii_arguments_same": verdict.pii_arguments_same,
            "answer_same": verdict.answer_same,
            "residual": verdict.residual,
            "plain_called": verdict.plain_called,
            "masked_called": verdict.masked_called,
            "control_matches_corpus": verdict.control_matches_corpus,
            "divergences": [asdict(one) for one in verdict.divergences],
        }
    return payload


def _replay_arm(name: str, calls: list[dict[str, object]]) -> ArmResult:
    """An `ArmResult` carrying only what the comparator reads. `final_text` is
    empty on purpose — `answer_same` is carried, never re-derived from a blank."""
    return ArmResult(
        arm=name,
        calls=tuple(ObservedCall(name=str(call["name"]),
                                 arguments=dict(call["arguments"]))
                    for call in calls),
        final_text="", cost_usd=0.0, model="", turns=0, duration_ms=0,
        is_error=False, subtype="success", api_error_status=None, errors=(),
        session_id="")


# --- the report -------------------------------------------------------------

def _report(payload: dict[str, object], coverage: dict[str, list[str]],
            dump: int) -> int:
    records = payload["cases"]
    assert isinstance(records, list)
    complete = [one for one in records if one.get("status") == "complete"]
    incomplete = [one for one in records if one.get("status") != "complete"]

    print()
    print("=" * 78)
    print(f"AgentPII-RU v2 · ЖИВАЯ ОСЬ (прозрачность) · {payload['model']}")
    print(f"прогон {payload['run_id']} · рубеж {payload['tier']} · "
          f"зерно {payload['seed']} · {len(records)} случаев")
    print("=" * 78)

    # --- 1. COST, printed first because it is what decides the next rung -----
    costs = [float(one["cost_usd"]) for one in complete]
    print("\n1. ЦЕНА — измеренная, не оценённая")
    ceiling = float(payload["ceiling_usd"])
    share = (f"{100.0 * float(payload['spent_usd']) / ceiling:.1f}%" if ceiling > 0
             else "потолок нулевой — ни один случай не мог быть допущен")
    print(f"   потолок ${ceiling:.2f} · "
          f"израсходовано ${float(payload['spent_usd']):.4f} ({share})")
    if costs:
        arms = int(payload["arms_per_case"])
        print(f"   на случай ({arms} плеча): среднее ${statistics.mean(costs):.4f} · "
              f"медиана ${statistics.median(costs):.4f} · "
              f"мин ${min(costs):.4f} · макс ${max(costs):.4f}")
        per_arm: Counter[str] = Counter()
        arm_count: Counter[str] = Counter()
        for one in complete:
            for arm in one["arms"]:
                per_arm[arm["arm"]] += float(arm["cost_usd"])
                arm_count[arm["arm"]] += 1
        for name in sorted(per_arm):
            print(f"     плечо {name:<7} ${per_arm[name] / arm_count[name]:.4f} "
                  f"среднее по {arm_count[name]}")
        by_rung: dict[str, list[float]] = {}
        for one in complete:
            by_rung.setdefault(str(one["length_rung"]), []).append(float(one["cost_usd"]))
        for rung in sorted(by_rung):
            values = by_rung[rung]
            print(f"     длина {rung:<7} ${statistics.mean(values):.4f} "
                  f"среднее по {len(values)}")
        print("   ПРОЕКЦИЯ следующих рубежей по этой средней "
              "(верхняя оценка: длинные случаи дороже и их доля растёт)")
        for name, size in sample.LIVE_TIERS.items():
            if size and size > len(records):
                print(f"     {name:<7} {size:>4} случаев ≈ "
                      f"${statistics.mean(costs) * size:.2f}")

    # --- 2. transparency ----------------------------------------------------
    print("\n2. ПРОЗРАЧНОСТЬ — тот же инструмент и те же аргументы, что без маскирования")
    if not complete:
        print("   ни один случай не завершился — числа нет")
    else:
        transparent = [one for one in complete if one["verdict"]["transparent"]]
        on_pii = [one for one in complete
                  if one["verdict"].get("transparent_on_pii")]
        print(f"   строго — любой аргумент:            {len(transparent)}/{len(complete)}"
              f" = {100.0 * len(transparent) / len(complete):.1f}%")
        print(f"   по аргументам, несущим ПД:          {len(on_pii)}/{len(complete)}"
              f" = {100.0 * len(on_pii) / len(complete):.1f}%")
        print("   ДВА ЧИСЛА, НИКОГДА НЕ ОДНО. Строгое отвечает «изменилось ли "
              "что-нибудь»;")
        print("   второе — «изменилось ли ЗНАЧЕНИЕ ЧЕЛОВЕКА», и только оно — дело "
              "продукта.")
        tools = sum(1 for one in complete if one["verdict"]["tools_same"])
        args = sum(1 for one in complete if one["verdict"]["arguments_same"])
        pii_args = sum(1 for one in complete
                       if one["verdict"].get("pii_arguments_same"))
        print(f"     тот же инструмент         {tools}/{len(complete)}")
        print(f"     те же аргументы (все)     {args}/{len(complete)}")
        print(f"     те же аргументы (ПД)      {pii_args}/{len(complete)}")
        answers = [one for one in complete if one["verdict"]["answer_same"] is not None]
        if answers:
            same = sum(1 for one in answers if one["verdict"]["answer_same"])
            print(f"     тот же ответ (`compare`) {same}/{len(answers)}")
        kinds: Counter[str] = Counter()
        for one in complete:
            for divergence in one["verdict"]["divergences"]:
                kinds[str(divergence["kind"])] += 1
        if kinds:
            print("   классы расхождений (одно расхождение — одна строка, не один случай):")
            for kind, count in kinds.most_common():
                print(f"     {kind:<20} {count}")
        # Per-stratum, printed as COUNTS: at these sizes a rate over three cases
        # is a number that reads like evidence and is not one.
        for axis in ("family", "register"):
            groups: dict[str, list[dict[str, object]]] = {}
            for one in complete:
                groups.setdefault(str(one[axis]), []).append(one)
            print(f"   по срезу `{axis}` (счёт, не доля):")
            for name in sorted(groups):
                rows = groups[name]
                ok = sum(1 for one in rows if one["verdict"]["transparent"])
                pii_ok = sum(1 for one in rows
                             if one["verdict"].get("transparent_on_pii"))
                print(f"     {name:<12} строго {ok}/{len(rows)} · ПД {pii_ok}/{len(rows)}")

    # --- 3. the floor -------------------------------------------------------
    controls = [one for one in complete if "self_control" in one]
    print("\n3. СОБСТВЕННЫЙ РАЗБРОС МОДЕЛИ — пол под числом выше")
    if not controls:
        print("   не мерился (--self-control выключен). Без него число выше нельзя")
        print("   отличить от модели, которая на столько же расходится сама с собой.")
    else:
        agree = sum(1 for one in controls if one["self_control"]["transparent"])
        agree_pii = sum(1 for one in controls
                        if one["self_control"].get("transparent_on_pii"))
        print(f"   чистый против чистого: строго {agree}/{len(controls)} = "
              f"{100.0 * agree / len(controls):.1f}% · "
              f"ПД {agree_pii}/{len(controls)} = "
              f"{100.0 * agree_pii / len(controls):.1f}%")
        print("   расхождение шлюза имеет смысл только НИЖЕ этого числа.")

    # --- 4. the capability control -----------------------------------------
    judged = [one for one in complete
              if one["verdict"]["control_matches_corpus"] is not None]
    print("\n4. КОНТРОЛЬ СПОСОБНОСТИ — попало ли ЧИСТОЕ плечо в ожидание корпуса")
    if judged:
        hit = sum(1 for one in judged if one["verdict"]["control_matches_corpus"])
        print(f"   {hit}/{len(judged)} · остальные {len(complete) - len(judged)} "
              f"случаев не несут `calls` и здесь не судятся")
    else:
        print("   ни один случай выборки не несёт ожидаемого вызова")

    # --- 5. what did not run ------------------------------------------------
    print("\n5. ЧЕГО ПРОГОН НЕ ПОКРЫЛ")
    for axis, missing in coverage.items():
        print(f"   {axis}: {', '.join(missing) if missing else '—'}")
    if incomplete:
        print(f"   НЕЗАВЕРШЁННЫХ {len(incomplete)} (учтены, не выброшены):")
        for one in incomplete[:dump]:
            print(f"     {one['id']}: {one.get('reason')}")

    # --- 6. fragility -------------------------------------------------------
    print("\n6. ЧТО ДЕЛАЛО ПРОГОН ХРУПКИМ")
    troubles: Counter[str] = Counter()
    for one in records:
        for arm in one.get("arms") or []:
            if arm["is_error"]:
                troubles[f"плечо {arm['arm']}: {arm['subtype']}"] += 1
            if arm["api_error_status"]:
                troubles[f"HTTP {arm['api_error_status']}"] += 1
            for error in arm["errors"]:
                troubles[str(error)[:60]] += 1
        if one.get("status") != "complete":
            troubles[str(one.get("reason", ""))[:60]] += 1
    if troubles:
        for name, count in troubles.most_common():
            print(f"   {name}: {count}")
    else:
        print("   ничего: ни одной ошибки API, ни одного таймаута, ни одного отказа")
    walls = [float(one["wall_s"]) for one in complete]
    if walls:
        print(f"   стена на случай: медиана {statistics.median(walls):.1f}s · "
              f"макс {max(walls):.1f}s")

    # --- 7. examples --------------------------------------------------------
    broken = [one for one in complete if not one["verdict"]["transparent"]]
    if broken:
        print(f"\n7. РАСХОЖДЕНИЯ, до {dump}")
        for one in broken[:dump]:
            print(f"   {one['id']} [{one['family']}/{one['register']}]")
            for divergence in one["verdict"]["divergences"][:6]:
                print(f"     {divergence['kind']}/{divergence['attribution']} "
                      f"{divergence['tool']}.{divergence['key']}: "
                      f"{divergence['plain']!r} -> {divergence['masked']!r}")
    print()
    return 0 if not incomplete else 1


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="?",
                        default=str(here.parent / "corpus.json"))
    parser.add_argument("--tier", default="nano",
                        help="|".join(sample.LIVE_TIERS))
    parser.add_argument("--ids", default="",
                        help="запятые: точный список случаев, для воспроизведения прогона")
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--ceiling", type=float, default=2.0, help="потолок трат, USD")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=300.0, help="на одно плечо")
    parser.add_argument("--self-control", action="store_true",
                        help="третье плечо: чистый прогон дважды, пол под прозрачностью")
    parser.add_argument("--out", default=str(here / "runs"))
    parser.add_argument("--dump", type=int, default=10)
    parser.add_argument("--rescore", default="",
                        help="пересудить сохранённый прогон новым компаратором, "
                             "без модели и без трат")
    args = parser.parse_args()

    try:
        everything = build.hydrated(build.load(Path(args.corpus)))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"корпус не читается: {error}", file=sys.stderr)
        return 2

    if args.rescore:
        source = Path(args.rescore)
        payload = _rescore(json.loads(source.read_text(encoding="utf-8")), everything)
        payload["rescored_from"] = str(source)
        target = source.with_suffix(".rescored.json")
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        coverage = sample.coverage(
            [case for case in everything
             if case.id in set(payload["ids"])], everything)  # type: ignore[arg-type]
        code = _report(payload, coverage, args.dump)
        print(f"пересуждено: {target}")
        return code

    if args.ids:
        wanted = [one.strip() for one in args.ids.split(",") if one.strip()]
        by_id = {case.id: case for case in everything}
        missing = [one for one in wanted if one not in by_id]
        if missing:
            print(f"нет таких случаев: {missing}", file=sys.stderr)
            return 2
        cases = [by_id[one] for one in wanted]
    else:
        if args.tier not in sample.LIVE_TIERS:
            print(f"неизвестный рубеж {args.tier!r}", file=sys.stderr)
            return 2
        cases = sample.draw(everything, sample.LIVE_TIERS[args.tier], args.seed)
    if not cases:
        print("выборка пуста", file=sys.stderr)
        return 2

    # A `preceded_by` lead is masked into the same vault WITHOUT a model call.
    # The claim it supports is about the vault, and running it live would double
    # its cost to measure nothing.
    by_id = {case.id: case for case in everything}
    leads = {case.id: by_id[case.preceded_by] for case in cases
             if case.preceded_by and case.preceded_by in by_id}

    load_dev_bundle()
    detector = _MemoDetector(Detector())
    run_id = str(uuid.uuid4())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    budget = Budget(out / f"{run_id}.spend.tsv", args.ceiling)

    print(f"прогон {run_id} · {args.model} · {len(cases)} случаев · "
          f"потолок ${args.ceiling:.2f} · плеч на случай "
          f"{3 if args.self_control else 2}", flush=True)
    started = datetime.now(timezone.utc).isoformat()
    records = asyncio.run(_drive(cases, leads, detector, budget, args.model, run_id,
                                 args.timeout, args.self_control, args.concurrency))

    payload: dict[str, object] = {
        "run_id": run_id, "model": args.model, "tier": args.tier if not args.ids else "ids",
        "seed": args.seed, "started": started,
        "finished": datetime.now(timezone.utc).isoformat(),
        "ceiling_usd": args.ceiling, "spent_usd": round(budget.committed, 6),
        "arms_per_case": 3 if args.self_control else 2,
        "ids": [case.id for case in cases], "cases": records,
    }
    coverage = sample.coverage(cases, everything)
    payload["coverage"] = coverage
    (out / f"{run_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    code = _report(payload, coverage, args.dump)
    print(f"результат: {out / (run_id + '.json')}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
