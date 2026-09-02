"""The live three-arm runner: C, then I ∥ C′, one case at a time, under one ledger.

    python3 bench/agentpii4/harness.py corpus.json --tier nano --repeats 1 --ceiling 12
    python3 bench/agentpii4/harness.py --report bench/runs/<date>/v4-live-nano/<run>.arms.jsonl

WHAT ONE TRIPLE IS. The same case is played three times against the same
model: C reads the real text and its calls go to a fresh mock untouched; I
reads the text through `RealGateway` (the production masking path) and its
calls are detokenised before they reach an identical fresh mock; C′ is a
second control. The effect of the gateway is agreement(I, C) minus
agreement(C′, C) — the model's own noise, subtracted on the same case. C runs
FIRST and alone: a control that did not finish has nothing to compare against,
and running the other two arms would spend money to measure nothing.

WHAT THE MOCK IS FOR. Every tool has a strict parser from a real RU API's own
documentation and a state that the calls mutate; the comparator reads the
STATE, not the argument strings. A parser that refuses a fake in I and
accepts the real value in C is a `validated_refused` — the class the engine
cannot fix by construction, printed apart from what it can.

MONEY. One `SpendLedger` for the agent and the judge, the invariant
`committed + reserved <= ceiling` at every instant. A triple reserves
cap × 3 before its first token and settles what the SDK actually billed;
a triple the ledger would not admit is RECORDED as refused, never dropped —
a run that sheds what it cannot afford reports only the cheap cases.

Lifted from `bench/agentpii3/live/run.py` (the SDK options, the termination
mapping, the cost bookkeeping) and changed in one place: the MCP handler runs
the MOCK, so the tool result is produced by the call, not scripted by the
corpus, and it passes through the gateway before the model reads it.
"""
import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parents[2]))          # prototype/, for pseudex

from bench.agentpii3 import score  # noqa: E402
from bench.agentpii3.live import judge as judge_mod  # noqa: E402
from bench.agentpii4 import report  # noqa: E402
from bench.agentpii4.compare import ArmRun, ObservedCall, pair_runs, substitutes_for  # noqa: E402
from bench.agentpii4.fake_agent import seed_backend  # noqa: E402
from bench.agentpii4.gateway import HarnessError, PassThrough, RealGateway  # noqa: E402
from bench.agentpii4.records import ArmMeta, arm_from_record, arm_record  # noqa: E402
from bench.agentpii4.schema import (  # noqa: E402
    EXCLUDED_TERMINATIONS, ARMS, Case, Ladder, case_from_json, corpus_digest, tier)
from pseudex.audit import AuditLog  # noqa: E402
from pseudex.detect_all import Detector  # noqa: E402
from pseudex.maskcache import MaskCache  # noqa: E402
from pseudex.redact import residual_tokens  # noqa: E402
from pseudex.vault import Vault  # noqa: E402
from testkit import load_dev_bundle  # noqa: E402

AGENT_MODEL: str = judge_mod.AGENT_MODEL
JUDGE_MODEL: str = judge_mod.JUDGE_MODEL

SERVER = "bench"
_PREFIX = f"mcp__{SERVER}__"
_NAMESPACE = uuid.UUID("6f0c2a4e-9d31-4b7a-8e55-2c1f7a9b3d10")
_ORG = "agentpii4-live"

# THE PER-ARM CAP THE SDK ENFORCES. A v4 case carries one to four user turns
# and offers up to five tools with schemas of a few hundred tokens each, so the
# cost sits in the prompt, not the answer. Anchored to the v3 measurement
# ($0.0134 for a one-turn arm, 30.08.2026) and printed by every run in the cost
# section, which is where the next run's cap comes from.
CAP_BASE_USD: float = 0.12
CAP_PER_TURN_USD: float = 0.04
CAP_PER_TOOL_USD: float = 0.01
SECONDS_BASE: float = 120.0
SECONDS_PER_TURN: float = 30.0

FILLER_RESULT = '{"status": "ok"}'


@dataclass
class ArmOutcome:
    run: ArmRun
    meta: ArmMeta


def cap_usd(case: Case) -> float:
    turns = sum(1 for message in case.messages if message.role == "user")
    return CAP_BASE_USD + CAP_PER_TURN_USD * max(0, turns - 1) + CAP_PER_TOOL_USD * len(case.tools)


def _timeout(case: Case) -> float:
    turns = sum(1 for message in case.messages if message.role == "user")
    return SECONDS_BASE + SECONDS_PER_TURN * turns


def session_id(run_id: str, case_id: str, arm: str, repeat: int) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{run_id}|{case_id}|{arm}|{repeat}"))


def _termination(result: ResultMessage | None) -> str:
    if result is None:
        return "harness_error"
    if not result.is_error and result.subtype == "success":
        return "done"
    if "max_turns" in result.subtype or "max_budget" in result.subtype:
        return "max_steps"
    return "provider_error"


def _mcp_tools(case: Case, gateway: object, backend: object, masked: list[dict[str, object]],
               sink: list[ObservedCall]) -> list[object]:
    """One in-process MCP tool per function the case offers, over the MOCK.

    restore -> backend.call -> serialise -> push_tool: the same four steps the
    scripted agent takes in `fake_agent.scripted_run`, so a verdict the smoke
    run produced is reachable here by the same path.
    """
    built: list[object] = []
    for schema_ in masked:
        function = schema_.get("function")
        if not isinstance(function, dict):
            continue
        name = str(function.get("name", ""))
        description = str(function.get("description", "") or name)
        parameters = function.get("parameters")
        parameters = parameters if isinstance(parameters, dict) else {"type": "object", "properties": {}}

        def make(tool_name: str) -> object:
            async def handler(args: dict[str, object]) -> dict[str, object]:
                arguments = dict(args)
                gateway.note_tool_call(tool_name, arguments)  # type: ignore[attr-defined]
                try:
                    restored, residual = gateway.restore_arguments(arguments)  # type: ignore[attr-defined]
                except HarnessError as broken:
                    gateway.fault(str(broken))  # type: ignore[attr-defined]
                    return {"content": [{"type": "text", "text": FILLER_RESULT}]}
                log = backend.call(tool_name, restored)  # type: ignore[attr-defined]
                sink.append(ObservedCall(
                    name=tool_name, written=arguments, restored=restored, residual=residual,
                    refusal_path=log.refusal.path if log.refusal else "",
                    refusal_rule=log.refusal.rule if log.refusal else "",
                    parsed=log.parsed, seq=len(sink) + 1))
                try:
                    served = gateway.push_tool(tool_name, log.result_text)  # type: ignore[attr-defined]
                except HarnessError as broken:
                    gateway.fault(str(broken))  # type: ignore[attr-defined]
                    return {"content": [{"type": "text", "text": FILLER_RESULT}]}
                # A refusal is a tool ERROR, exactly as the real API answers:
                # the model sees the documented rule and may retry or give up.
                return {"content": [{"type": "text", "text": served}], "is_error": log.refusal is not None}
            return tool(tool_name, description, parameters)(handler)

        built.append(make(name))
    return built


def _options(case: Case, model: str, cap: float, sid: str, servers: dict[str, object],
             allowed: list[str], system: str, workdir: str) -> ClaudeAgentOptions:
    env = {key: value for key, value in os.environ.items() if key != "CLAUDECODE"}
    turns = sum(1 for message in case.messages if message.role == "user")
    return ClaudeAgentOptions(
        model=model, tools=[], mcp_servers=servers, allowed_tools=allowed,
        strict_mcp_config=True, setting_sources=[], permission_mode="bypassPermissions",
        system_prompt=system, max_turns=3 * turns + 10, max_budget_usd=cap,
        session_id=sid, cwd=workdir, env=env)


async def run_arm(case: Case, arm: str, repeat: int, gateway: object, backend: object,
                  model: str, cap: float, run_id: str) -> ArmOutcome:
    """One arm of one case against the real model. Raises `asyncio.TimeoutError`
    (not caught here — a timed-out run has no measured cost) and `HarnessError`."""
    calls: list[ObservedCall] = []
    system = gateway.push_system(case.messages[0].content)  # type: ignore[attr-defined]
    masked = gateway.tools()  # type: ignore[attr-defined]
    server = create_sdk_mcp_server(SERVER, tools=_mcp_tools(case, gateway, backend, masked, calls))
    allowed = [_PREFIX + str(one["function"]["name"]) for one in masked  # type: ignore[index]
               if isinstance(one.get("function"), dict)]
    sid = session_id(run_id, case.id, arm, repeat)
    workdir = tempfile.mkdtemp(prefix="agentpii4-live-")
    options = _options(case, model, cap, sid, {SERVER: server}, allowed, system, workdir)

    replies: list[str] = []
    result: ResultMessage | None = None
    failed: ResultMessage | None = None
    turns = 0
    model_name = model

    async def drive() -> None:
        nonlocal result, failed, turns, model_name
        async with ClaudeSDKClient(options=options) as client:
            for index, message in enumerate(case.messages):
                if message.role != "user":
                    continue
                await client.query(gateway.push_user(index))  # type: ignore[attr-defined]
                turn: list[str] = []
                async for reply in client.receive_response():
                    if isinstance(reply, AssistantMessage):
                        text = "".join(block.text for block in reply.content if isinstance(block, TextBlock))
                        if text:
                            turn.append(text)
                    elif isinstance(reply, ResultMessage):
                        result = reply
                        turns += int(reply.num_turns)
                        if failed is None and (reply.is_error or reply.subtype != "success"):
                            failed = reply
                        if reply.model_usage:
                            model_name = max(
                                reply.model_usage.items(),
                                key=lambda row: float((row[1] or {}).get("costUSD", 0.0)
                                                      if isinstance(row[1], dict) else 0.0))[0]
                joined = "\n".join(turn)
                replies.append(joined)
                if joined:
                    gateway.note(joined)  # type: ignore[attr-defined]

    await asyncio.wait_for(drive(), timeout=_timeout(case))
    if gateway.faults:  # type: ignore[attr-defined]
        raise HarnessError(f"{case.id}/{arm}: {gateway.faults[0]}")  # type: ignore[attr-defined]
    if result is None:
        raise HarnessError(f"{case.id}/{arm}: поток закончился без ResultMessage")
    worst = failed or result
    raw_reply = next((one for one in reversed(replies) if one.strip()), "")
    reply = gateway.restore_text(raw_reply) if raw_reply else ""  # type: ignore[attr-defined]
    substitutes = substitutes_for(case, gateway.substitutes_seen()) if arm == "I" else {}  # type: ignore[attr-defined]
    run = ArmRun(case_id=case.id, arm=arm, repeat=repeat, calls=tuple(calls),
                 state=backend.snapshot(), reply=reply,  # type: ignore[attr-defined]
                 termination=_termination(worst), cost_usd=float(result.total_cost_usd or 0.0),
                 substitutes=substitutes)
    meta = ArmMeta(model=model_name, turns=turns, duration_ms=int(result.duration_ms), session_id=sid,
                   subtype=str(worst.subtype), is_error=bool(worst.is_error),
                   api_error_status=worst.api_error_status,
                   errors=tuple(str(one) for one in (worst.errors or ())), reason="", cap_usd=cap)
    return ArmOutcome(run, meta)


def _failed_arm(case: Case, arm: str, repeat: int, termination: str, reason: str, cap: float,
                cost: float, run_id: str) -> ArmOutcome:
    run = ArmRun(case_id=case.id, arm=arm, repeat=repeat, calls=(), state=(), reply="",
                 termination=termination, cost_usd=cost)
    meta = ArmMeta(model="", turns=0, duration_ms=0, session_id=session_id(run_id, case.id, arm, repeat),
                   subtype="", is_error=True, api_error_status=None, errors=(), reason=reason, cap_usd=cap)
    return ArmOutcome(run, meta)


async def _guarded_arm(case: Case, arm: str, repeat: int, gateway: object, backend: object,
                       model: str, cap: float, run_id: str) -> ArmOutcome:
    """Never raises for one arm: every failure becomes a termination + reason.
    A timed-out arm is charged its FULL cap — it did bill, and a ledger that
    books it at zero lets the next case spend money already gone."""
    try:
        return await run_arm(case, arm, repeat, gateway, backend, model, cap, run_id)
    except asyncio.TimeoutError:
        return _failed_arm(case, arm, repeat, "timeout", f"таймаут {_timeout(case):.0f}s", cap, cap, run_id)
    except HarnessError as broken:
        return _failed_arm(case, arm, repeat, "harness_error", f"HarnessError: {broken}", cap, 0.0, run_id)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as broken:
        # An exception out of the masking path itself is the PRODUCT failing
        # closed — counted as `gateway_5xx`, not excluded.
        kind = "gateway_5xx" if arm == "I" else "harness_error"
        return _failed_arm(case, arm, repeat, kind, f"{type(broken).__name__}: {broken}", cap, 0.0, run_id)


def _judge_request(case: Case, run: ArmRun, gateway: RealGateway) -> score.JudgeRequest:
    kinds = {item.canonical: item.type for item in case.pii}
    kinds.update({item.value: item.type for item in case.pii})
    surviving = tuple(residual_tokens(run.reply, gateway.vault))
    folded = run.reply.casefold()
    missing = tuple(required for required in case.expects.must_contain
                    if required.casefold() not in folded)
    return score.JudgeRequest(
        case_id=case.id,
        question="остались ли настоящие ПД в ответе клиенту, и не выдана ли подмена за настоящее значение",
        answer=run.reply, must_contain=case.expects.must_contain,
        must_not_contain=case.expects.must_not_contain, closed_answer="",
        substitutes_present=surviving, substitutes_minted=gateway.substitutes(),
        residual_present=tuple(value for value in surviving if value.startswith("REDACTED")),
        missing=missing)


async def _judge(case: Case, run: ArmRun, gateway: RealGateway, config: judge_mod.JudgeConfig | None,
                 ) -> dict[str, object]:
    """The deterministic floor, raised by whatever the model could prove —
    the same composition as v3's `_judge_answer`, on the I arm's reply only."""
    request = _judge_request(case, run, gateway)
    base = score.deterministic_judge(request)
    if config is None or not run.reply.strip():
        return {"verdict": base.verdict, "why": base.why, "judged_by": base.judged_by,
                "missing": list(request.missing), "cost_usd": 0.0}
    # ALL minted substitutes, not only the ones string search already found in
    # the reply — the half the judge exists for is the half the vault could not
    # match (an inflected or paraphrased substitute). With the matched-only
    # source the nano pilot asked the model nothing and reported 27 «clean» at
    # $0.00: a deterministic floor wearing the judge's name.
    under = judge_mod.case_under_judgement(request, lambda _r: tuple(gateway.substitutes()))
    try:
        judgement = await judge_mod.judge_answer(under, judge_mod.oracle_literals(request), config)
    except (judge_mod.BudgetExhausted, judge_mod.JudgeCallFailed) as stopped:
        verdict = base if base.verdict not in ("clean", score.UNJUDGED) else score.JudgeVerdict(
            verdict=score.UNJUDGED, why=f"судья не ответил: {stopped}", judged_by="none")
        return {"verdict": verdict.verdict, "why": verdict.why, "judged_by": verdict.judged_by,
                "missing": list(request.missing), "cost_usd": 0.0}
    merged = judge_mod.merge(base, judgement)
    return {"verdict": merged.verdict, "why": merged.why, "judged_by": merged.judged_by,
            "missing": list(request.missing), "cost_usd": round(judgement.cost_usd, 6),
            "defect": judgement.defect(), "complete": judgement.complete()}


async def run_triple(case: Case, repeat: int, detector: Detector, ledger: judge_mod.SpendLedger,
                     config: judge_mod.JudgeConfig | None, model: str, run_id: str,
                     ) -> tuple[list[ArmOutcome], dict[str, object]]:
    cap = cap_usd(case)
    triple: dict[str, object] = {"case_id": case.id, "repeat": repeat, "kind": case.kind,
                                 "register": case.register, "cluster": case.cluster,
                                 "cap_usd": round(cap * 3, 6), "cost_usd": 0.0, "status": "refused",
                                 "reason": "", "arms": {}, "judge": {}}
    try:
        await ledger.reserve(cap * 3)
    except judge_mod.BudgetExhausted as exhausted:
        triple["reason"] = str(exhausted)
        return [], triple

    outcomes: list[ArmOutcome] = []
    spent = 0.0
    try:
        control = await _guarded_arm(case, "C", repeat, PassThrough(case), seed_backend(case), model, cap, run_id)
        outcomes.append(control)
        spent += control.run.cost_usd
        if control.run.termination in EXCLUDED_TERMINATIONS:
            triple["status"] = "excluded"
            triple["reason"] = f"C: {control.run.termination} {control.meta.reason}".strip()
            return outcomes, triple
        gateway = RealGateway(case, detector, Vault(":memory:", _ORG), AuditLog(":memory:"), MaskCache(256))
        intervention, second = await asyncio.gather(
            _guarded_arm(case, "I", repeat, gateway, seed_backend(case), model, cap, run_id),
            _guarded_arm(case, "C2", repeat, PassThrough(case), seed_backend(case), model, cap, run_id))
        outcomes.extend((intervention, second))
        spent += intervention.run.cost_usd + second.run.cost_usd
        excluded = [one.run.arm for one in outcomes if one.run.termination in EXCLUDED_TERMINATIONS]
        triple["status"] = "excluded" if excluded else "complete"
        triple["reason"] = " · ".join(f"{one.run.arm}: {one.meta.reason or one.run.termination}"
                                      for one in outcomes if one.run.termination in EXCLUDED_TERMINATIONS)
        if intervention.run.termination not in EXCLUDED_TERMINATIONS:
            triple["judge"] = await _judge(case, intervention.run, gateway, config)
    finally:
        await ledger.settle(f"agent/{case.id}/{repeat}", cap * 3, spent)
        triple["cost_usd"] = round(spent, 6)
        triple["arms"] = {one.run.arm: {"termination": one.run.termination, "cost_usd": round(one.run.cost_usd, 6),
                                        "calls": len(one.run.calls), "reason": one.meta.reason}
                          for one in outcomes}
    return outcomes, triple


async def drive(cases: list[Case], repeats: int, detector: Detector, ledger: judge_mod.SpendLedger,
                config: judge_mod.JudgeConfig | None, model: str, run_id: str, concurrency: int,
                arms_sink: Path, triples_sink: Path) -> tuple[list[ArmRun], list[dict[str, object]]]:
    limiter = asyncio.Semaphore(max(1, concurrency))
    by_id = {case.id: case for case in cases}
    jobs = [(case, repeat) for repeat in range(repeats) for case in cases]
    # Most-expensive-first: a reservation is held at full cap for the life of
    # a triple, and running the cheap ones first refuses the dear ones last.
    jobs.sort(key=lambda job: -cap_usd(job[0]))
    total = len(jobs)
    runs: list[ArmRun] = []
    triples: list[dict[str, object]] = []
    done = 0

    async def worker(case: Case, repeat: int) -> None:
        nonlocal done
        async with limiter:
            outcomes, triple = await run_triple(case, repeat, detector, ledger, config, model, run_id)
            # WRITTEN BEFORE ANYTHING ELSE: a shell timeout during the next
            # triple must not cost this one's result.
            with arms_sink.open("a", encoding="utf-8") as handle:
                for one in outcomes:
                    handle.write(json.dumps(arm_record(one.run, one.meta, by_id[case.id]), ensure_ascii=False) + "\n")
            with triples_sink.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(triple, ensure_ascii=False) + "\n")
            runs.extend(one.run for one in outcomes)
            triples.append(triple)
            done += 1
            judge = triple.get("judge") or {}
            print(f"  [{done}/{total}] {case.id}|{repeat} {triple['status']} "
                  f"${float(triple['cost_usd']):.4f} "
                  f"{' '.join(f'{arm}:{info['termination']}/{info['calls']}' for arm, info in dict(triple['arms']).items())} "  # type: ignore[union-attr]
                  f"судья={judge.get('verdict', '—')}", flush=True)

    await asyncio.gather(*(worker(case, repeat) for case, repeat in jobs))
    return runs, triples


def _load(path: Path) -> tuple[list[Case], str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = [case_from_json(one) for one in raw["corpus"]]
    return cases, str(raw.get("digest") or corpus_digest(cases))


def _ladder(path: Path) -> Ladder:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Ladder(version=int(raw["version"]), seed=int(raw["seed"]),
                  corpus_sha256=str(raw["corpus_sha256"]),
                  tiers={name: tuple(ids) for name, ids in dict(raw["tiers"]).items()})


def _cost_lines(triples: list[dict[str, object]], ceiling: float) -> list[str]:
    complete = [one for one in triples if one["status"] == "complete"]
    refused = [one for one in triples if one["status"] == "refused"]
    excluded = [one for one in triples if one["status"] == "excluded"]
    spent = sum(float(one["cost_usd"]) for one in triples)
    judge = sum(float((one.get("judge") or {}).get("cost_usd") or 0.0) for one in triples)  # type: ignore[union-attr]
    lines = ["0. ЦЕНА — измеренная (ResultMessage.total_cost_usd), не оценённая",
             f"   троек: полных {len(complete)} · исключено {len(excluded)} · не допущено потолком {len(refused)}",
             f"   потрачено ${spent:.2f} из ${ceiling:.2f} (судья ${judge:.2f} внутри)"]
    if complete:
        per = sorted(float(one["cost_usd"]) for one in complete)
        lines.append(f"   тройка: медиана ${per[len(per) // 2]:.4f} · макс ${per[-1]:.4f} · "
                     f"среднее ${sum(per) / len(per):.4f} — потолок на 120 троек × K: "
                     f"${sum(per) / len(per) * 120:.0f} × K")
    verdicts: dict[str, int] = {}
    for one in complete:
        verdict = str((one.get("judge") or {}).get("verdict", "—"))  # type: ignore[union-attr]
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
    lines.append("   ответ клиенту (плечо I, судья): " + " · ".join(f"{k} {v}" for k, v in sorted(verdicts.items())))
    return lines


def _render(by_id: dict[str, Case], runs: list[ArmRun], triples: list[dict[str, object]],
            payload: dict[str, object], dump: int) -> list[str]:
    paired, excluded = pair_runs(runs)
    scored = report.score_triples(by_id, paired)
    header = (f"AGENTPII-RU v4 · ЖИВОЙ ПРОГОН {payload.get('run_id', '')} · агент {payload.get('model', '')} · "
              f"судья {payload.get('judge_model', '')} · ярус {payload.get('tier', '')} · корпус {str(payload.get('digest', ''))[:12]}")
    lines = [header, ""]
    lines += _cost_lines(triples, float(payload.get("ceiling_usd") or 0.0))
    lines += [""]
    lines += report.render(by_id, scored, excluded, "ЭФФЕКТ ШЛЮЗА — три плеча, тот же мок", dump=dump)
    return lines


def main() -> int:
    here = _HERE.parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", nargs="?", default=str(here / "corpus.json"))
    parser.add_argument("--ladder", default=str(here / "ladder.json"))
    parser.add_argument("--tier", default="nano")
    parser.add_argument("--ids", default="", help="запятые: точный список случаев вместо яруса")
    parser.add_argument("--repeats", type=int, default=1, help="K повторов каждой тройки")
    parser.add_argument("--ceiling", type=float, default=12.0, help="потолок на весь прогон, USD (агент + судья)")
    parser.add_argument("--model", default=AGENT_MODEL)
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--no-judge", action="store_true", help="только детерминированный судья на ответе")
    parser.add_argument("--concurrency", type=int, default=2, help="троек одновременно (каждая — до двух плеч разом)")
    parser.add_argument("--out", default="")
    parser.add_argument("--dump", type=int, default=12)
    parser.add_argument("--report", default="", help="пересобрать отчёт из <run>.arms.jsonl без модели и без трат")
    args = parser.parse_args()

    if args.report and (Path(args.report).parent / "corpus.json").exists():
        # The snapshot taken at run time wins over whatever the tree holds now.
        args.corpus = str(Path(args.report).parent / "corpus.json")
    everything, digest = _load(Path(args.corpus))
    by_id = {case.id: case for case in everything}

    if args.report:
        source = Path(args.report)
        runs = [arm_from_record(json.loads(line)) for line in source.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        stem = source.name[:-len(".arms.jsonl")] if source.name.endswith(".arms.jsonl") else source.stem
        triples_path = source.with_name(stem + ".triples.jsonl")
        triples = ([json.loads(line) for line in triples_path.read_text(encoding="utf-8").splitlines() if line.strip()]
                   if triples_path.exists() else [])
        meta_path = source.with_name(stem + ".meta.json")
        payload = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"run_id": stem}
        for line in _render(by_id, runs, triples, payload, args.dump):
            print(line)
        return 0

    if args.ids:
        wanted = [one.strip() for one in args.ids.split(",") if one.strip()]
        missing = [one for one in wanted if one not in by_id]
        if missing:
            print(f"нет таких случаев: {missing}", file=sys.stderr)
            return 2
        cases = [by_id[one] for one in wanted]
        tier_name = "ids"
    else:
        cases = tier(everything, _ladder(Path(args.ladder)), args.tier)
        tier_name = args.tier
    if not cases:
        print("выборка пуста", file=sys.stderr)
        return 2

    load_dev_bundle()
    detector = Detector()
    run_id = str(uuid.uuid4())
    out = Path(args.out) if args.out else (here.parent / "runs" / datetime.now().strftime("%Y-%m-%d")
                                           / f"v4-live-{tier_name}")
    out.mkdir(parents=True, exist_ok=True)
    # THE CORPUS THE RUN SAW, beside the run: a later rebuild changes case text
    # and spans, and `--report` must replay against what was actually played.
    snapshot = out / "corpus.json"
    if not snapshot.exists():
        snapshot.write_text(Path(args.corpus).read_text(encoding="utf-8"), encoding="utf-8")
    arms_sink = out / f"{run_id}.arms.jsonl"
    triples_sink = out / f"{run_id}.triples.jsonl"
    ledger = judge_mod.SpendLedger(out / f"{run_id}.spend.tsv", args.ceiling)
    config = None if args.no_judge else judge_mod.JudgeConfig(
        model=args.judge_model, ledger=ledger, query_cap_usd=judge_mod.QUERY_CAP_USD,
        retries=judge_mod.RETRIES, trace_path=out / f"{run_id}.judge.jsonl")

    payload: dict[str, object] = {
        "run_id": run_id, "benchmark": "agentpii4", "model": args.model,
        "judge_model": "" if args.no_judge else args.judge_model, "tier": tier_name, "repeats": args.repeats,
        "digest": digest, "ceiling_usd": args.ceiling, "arms": list(ARMS),
        "cap_base_usd": CAP_BASE_USD, "started": datetime.now(timezone.utc).isoformat(),
        "ids": [case.id for case in cases], "spent_usd": 0.0,
    }
    # WRITTEN BEFORE THE FIRST DOLLAR.
    (out / f"{run_id}.meta.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"прогон {run_id} · агент {args.model} · судья {payload['judge_model'] or 'детерминированный'} · "
          f"{len(cases)} случаев × K={args.repeats} × 3 плеча · потолок ${args.ceiling:.2f}", flush=True)
    print(f"инкрементальная запись: {arms_sink}", flush=True)
    started = time.time()
    runs, triples = asyncio.run(drive(cases, args.repeats, detector, ledger, config, args.model, run_id,
                                      args.concurrency, arms_sink, triples_sink))
    payload["finished"] = datetime.now(timezone.utc).isoformat()
    payload["spent_usd"] = round(ledger.committed(), 6)
    payload["wall_s"] = round(time.time() - started, 1)
    lines = _render(by_id, runs, triples, payload, args.dump)
    payload["report"] = lines
    (out / f"{run_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / f"{run_id}.meta.json").write_text(json.dumps(
        {key: value for key, value in payload.items() if key != "report"}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print()
    for line in lines:
        print(line)
    print(f"\nрезультат: {out / (run_id + '.json')}")
    print(f"по плечам: {arms_sink}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
