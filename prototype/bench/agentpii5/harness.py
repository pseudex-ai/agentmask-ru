"""ЖИВОЙ ПРОГОН v5: три плеча, один мок, один потолок — и всё, что читают хопы.

    python3 -m bench.agentpii5.harness corpus.v5.json --tier nano --repeats 1 --ceiling 12
    python3 -m bench.agentpii5.harness --report bench/runs/<date>/v5-live-nano

ОДНА ТРОЙКА — та же, что в v4: C first and alone, then I ∥ C′, one
`SpendLedger` for the agent and the judge, a refused triple RECORDED and never
dropped. The controls go through v4's OWN `run_arm` with v4's `PassThrough`, on
purpose: the baseline this run is compared against must not move with the
treatment, and the surest way to keep it still is to run v4's code.

ЧТО ДОБАВЛЯЕТ v5, И ПОЧЕМУ ЭТО НЕЛЬЗЯ ПОСЧИТАТЬ ПОТОМ. A hop is a crossing of
one datum at one moment, and three of the four things it needs exist only
while the arm is live: WHICH turn a call happened in, WHAT the mock actually
returned (`text_real`, its slot tags and its return form), and WHICH substitute
the model READ in each message and each result. `GatewayV5` records them as
they pass; `observe.py` then reads records and never the engine.

ЭТО ЕДИНСТВЕННЫЙ МОДУЛЬ ПАКЕТА, КОТОРОМУ МОЖНО `import pseudex`
(`contracts.PSEUDEX_ALLOWED_MODULES`), потому что плечо I — ЭТО
производственный путь. `test_harness.test_only_harness_imports_pseudex` walks
the package with `ast` and refuses a second importer.

СТРИМИНГ — КОНТРАКТ, А НЕ ТРУБА. For a `streaming` case the raw reply is
restored twice: whole (`unmask_text`, what the report uses) and chunk by chunk
through `pseudex.redact.StreamDetokenizer` in 17-character pieces — a prime, so
no boundary can align with a token by luck. A difference between the two is
`stream_mismatch`: a defect of the streaming leg, counted apart and never
folded into the form lines (spec §3.7).
"""
import argparse
import ast
import asyncio
import hashlib
import json
import sys
import tempfile
import time
import traceback
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)

from bench.agentpii3 import score
from bench.agentpii3.live import judge as v3_judge
from bench.agentpii4 import harness as v4_harness
from bench.agentpii4.compare import ArmRun, ObservedCall, substitutes_for
from bench.agentpii4.gateway import HarnessError, PassThrough, RealGateway
from bench.agentpii4.mock import CallLog
from bench.agentpii4.records import ArmMeta, arm_record
from bench.agentpii4.schema import ARMS, EXCLUDED_TERMINATIONS, Ladder, tier
from bench.agentpii5 import records as r
from bench.agentpii5 import report as v5_report
from bench.agentpii5.contracts import (
    AGENT_MODEL, ECHO_TAG_PREFIX, JUDGE_MODEL, QUERY_CAP_USD, RETRIES, ArmRunV5,
    CalibrationStamp, CaseV5, HopObservation, JudgeInput, JudgeRow, JudgeVerdict,
    MentionRecord, ToolResultRecord)
from bench.agentpii5.judge import (
    JudgeConfig, build_prompt, judge_answer, judge_input, prompt_sha256, residual_pregate_of)
from bench.agentpii5.mock import BackendV5, seed_backend_v5
from bench.agentpii5.observe import observe
from bench.agentpii5.schema import case_v5_from_json, case_v5_to_json, corpus_digest_v5
from pseudex.audit import AuditLog
from pseudex.detect_all import Detector
from pseudex.maskcache import MaskCache
from pseudex.morph_places import strip_leading_city
from pseudex.redact import StreamDetokenizer, unmask_text
from pseudex.vault import Vault
from testkit import load_dev_bundle

_ORG = "agentpii5"
# A PRIME, so no chunk boundary can align with a token, a separator or a word
# by construction. 16 would split «+7 900 000-00-00» the same way on every
# phone in the corpus and a carry bug would hide behind the regularity.
STREAM_CHUNK: int = 17


@dataclass
class TripleResult:
    """Everything one triple produced, before anything is written.

    A dataclass rather than a tuple of five: `drive_v5` writes five files from
    it, and a positional tuple is where a writer starts putting the hops into
    the judge file.
    """

    outcomes: list[v4_harness.ArmOutcome]
    gateway_run: ArmRunV5 | None
    hops: tuple[HopObservation, ...]
    judge: JudgeRow | None
    triple: dict[str, object]


class TripleRunner(Protocol):
    """What `drive_v5` calls per (case, repeat).

    An explicit parameter rather than a module attribute a test monkeypatches:
    `test_harness.test_run_files_written` must drive the WRITER with canned
    arms, and a seam that exists only under a test is a seam nobody looked at.
    """

    async def __call__(self, case: CaseV5, repeat: int) -> TripleResult: ...


# --- the gateway that also remembers ----------------------------------------------------

class GatewayV5(RealGateway):
    """v4's production-path gateway, plus the record `observe.py` reads.

    Three things are captured that v4 threw away: the model REQUEST each
    message and result rode in (`request_index`, what `stability` and the
    memory hops key on), the tool result as the mock produced it and as the
    model read it (`ToolResultRecord`), and every substitute the model actually
    READ (`MentionRecord`) — including the second spelling of one substitute in
    a later message, which is the only way an answer span can be attributed
    back to an item.
    """

    def __init__(self, case: CaseV5, detector: Detector, vault: Vault, audit: AuditLog,
                 cache: MaskCache) -> None:
        super().__init__(case.base, detector, vault, audit, cache)
        self._case5 = case
        self._requests = 0
        self._mentions: list[MentionRecord] = []
        self._results: list[ToolResultRecord] = []

    @property
    def request_index(self) -> int:
        return self._requests

    def mentions(self) -> tuple[MentionRecord, ...]:
        return tuple(self._mentions)

    def tool_records(self) -> tuple[ToolResultRecord, ...]:
        return tuple(self._results)

    def _push(self, wire: dict[str, object], text: str, index: int | None) -> str:
        # The system prompt is not a request: it is the prompt every request
        # carries. Counting it would shift every `request_index` by one and
        # `_recall_request` would look one request too late.
        if not (index == 0 and str(wire.get("role")) == "system"):
            self._requests += 1
        served = super()._push(wire, text, index)
        if index is not None:
            self._note_message_mentions(index)
        return served

    def _note_message_mentions(self, index: int) -> None:
        """What the model read in place of each item of THIS message.

        `score._seen` is v4's own reader of a masked message, so a mention and
        `substitutes_seen` cannot disagree about what stood where.
        """
        masked = self._masked.get(index)
        if masked is None:
            return
        for item in self._case5.base.pii:
            if item.where.kind != "message" or item.where.msg != index:
                continue
            surface = score._seen(masked, item.where.start, item.where.end)
            if surface and surface != item.value:
                self._mentions.append(MentionRecord(
                    item_id=item.id, msg=index, result_seq=-1, substitute=surface,
                    request_index=self._requests))

    def push_call(self, name: str, log: CallLog, return_form: str, turn: int,
                  ordinal: int) -> str:
        """A tool result, masked for the model AND recorded as a crossing.

        The mock's slot tags (`CallLog.result_spans`) are item ids, so a hop is
        resolved by id and never by searching the text for a value — the search
        is what made v4 attribute one person's phone to another when two
        records shared it.
        """
        served = self.push_tool(name, log.result_text)
        masked = self._tool_results[-1]
        spans = {str(tag): (int(span[0]), int(span[1]))
                 for tag, span in log.result_spans.items()}
        self._results.append(ToolResultRecord(
            tool_name=name, seq=log.seq, call_ordinal=ordinal, turn=turn,
            return_form=return_form, text_real=masked.text, text_masked=masked.masked,
            spans_real=spans,
            pieces=tuple((piece.start, piece.end, piece.substitute, piece.engine_type)
                         for piece in masked.pieces),
            # A SCRIPTED error parses nothing and refuses nothing — the mock
            # answered before the parser ran. A documented parse refusal is also
            # `error_with_value` (ruling R-18) but carries its `Refusal`, so the
            # two are told apart by the refusal and not by the form.
            forced=log.parsed is None and log.refusal is None))
        for tag, (start, end) in spans.items():
            item_id = tag[len(ECHO_TAG_PREFIX):] if tag.startswith(ECHO_TAG_PREFIX) else tag
            covering = next((piece for piece in masked.pieces
                             if piece.start < end and start < piece.end), None)
            if covering is not None:
                self._mentions.append(MentionRecord(
                    item_id=item_id, msg=-1, result_seq=log.seq, substitute=covering.substitute,
                    request_index=self._requests))
        return served


def real_parts_of(case: CaseV5) -> tuple[str, ...]:
    """The customer's OWN parts — never counted as a substitute of ours.

    The settlement inside a minted address is real (vault `_settlement_of`), so
    without this the pre-gate would call every reply that names the customer's
    own town «неверно».
    """
    return tuple(sorted({part for item in case.base.pii for part in item.parts.values() if part}))


def minted_substitutes(gateway: RealGateway) -> tuple[str, ...]:
    """The minted list the pre-gate hunts, with the real city stripped out of
    every address — v4's `_judge_request` rule, applied HERE so it cannot be
    bypassed one call later the way v4's was on its 06.09 run."""
    return tuple(strip_leading_city(value) if "," in value else value
                 for value in gateway.substitutes())


# --- the streaming leg -------------------------------------------------------------------

def restore_stream(text: str, vault: Vault, chunk: int) -> str:
    """The reply restored through the sidecar's per-field chunk contract.

    ONE detokenizer for the whole stream: the carry is what lets a substitute
    split across two chunks resolve at all, and a fresh object per chunk is
    exactly the bug this leg exists to catch.
    """
    stream = StreamDetokenizer(vault)
    out = [stream.feed(text[at:at + chunk]) for at in range(0, len(text), chunk)]
    out.append(stream.flush())
    return "".join(out)


def stream_verdict(raw: str, vault: Vault) -> tuple[str, bool]:
    """(whole-text restoration, does the chunked one differ). The whole text is
    what the report reads; the difference is the product defect."""
    whole = unmask_text(raw, vault)
    return whole, restore_stream(raw, vault, STREAM_CHUNK) != whole


# --- one gateway arm ----------------------------------------------------------------------

def _mcp_tools_v5(gateway: GatewayV5, backend: BackendV5, masked: list[dict[str, object]],
                  sink: list[ObservedCall], turns: list[int], clock: list[int]) -> list[object]:
    """v4's MCP handler with the turn, the ordinal and the return form recorded.

    v4's `_mcp_tools` is not parameterised for this and v5 never edits v4, so
    the four steps (restore → call → serialise → push) are repeated here and the
    fifth — record WHEN and IN WHAT FORM — is added.
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
                gateway.note_tool_call(tool_name, arguments)
                turn = clock[0]
                try:
                    restored, residual = gateway.restore_arguments(arguments)
                except HarnessError as broken:
                    gateway.fault(str(broken))
                    return {"content": [{"type": "text", "text": v4_harness.FILLER_RESULT}]}
                except Exception as broken:            # noqa: BLE001 — the product failing in the SDK
                    gateway.fault(f"restore_arguments raised {type(broken).__name__}: {broken}\n"
                                  + traceback.format_exc())
                    print(f"FAULT {tool_name} restore_arguments: {broken}", file=sys.stderr)
                    return {"content": [{"type": "text", "text": v4_harness.FILLER_RESULT}]}
                log = backend.call(tool_name, restored)
                ordinal = sum(1 for index, call in enumerate(sink)
                              if call.name == tool_name and turns[index] == turn)
                sink.append(ObservedCall(
                    name=tool_name, written=arguments, restored=restored, residual=residual,
                    refusal_path=log.refusal.path if log.refusal else "",
                    refusal_rule=log.refusal.rule if log.refusal else "",
                    parsed=log.parsed, seq=len(sink) + 1))
                turns.append(turn)
                try:
                    served = gateway.push_call(tool_name, log, backend.form_of(log.seq), turn, ordinal)
                except HarnessError as broken:
                    gateway.fault(str(broken))
                    return {"content": [{"type": "text", "text": v4_harness.FILLER_RESULT}]}
                except Exception as broken:            # noqa: BLE001 — same, on the result leg
                    gateway.fault(f"push_call raised {type(broken).__name__}: {broken}\n"
                                  + traceback.format_exc())
                    print(f"FAULT {tool_name} push_call: {broken}", file=sys.stderr)
                    return {"content": [{"type": "text", "text": v4_harness.FILLER_RESULT}]}
                return {"content": [{"type": "text", "text": served}],
                        "is_error": log.refusal is not None}
            return tool(tool_name, description, parameters)(handler)

        built.append(make(name))
    return built


@dataclass
class ArmOutcomeV5:
    base: v4_harness.ArmOutcome
    run: ArmRunV5


async def run_arm_v5(case: CaseV5, arm: str, repeat: int, gateway: GatewayV5,
                     backend: BackendV5, model: str, cap: float, run_id: str) -> ArmOutcomeV5:
    """The GATEWAY arm of one case against the real model.

    Only the gateway arm: a control has no substitutes to observe, so it runs
    through v4's own `run_arm` and its record stays byte-identical to v4's.
    Raises `asyncio.TimeoutError` and `HarnessError` exactly as v4 does — a
    timed-out run has no measured cost and `_guarded_arm_v5` charges the cap.
    """
    calls: list[ObservedCall] = []
    call_turns: list[int] = []
    clock = [0]
    system = gateway.push_system(case.base.messages[0].content)
    masked = gateway.tools()
    server = create_sdk_mcp_server(
        v4_harness.SERVER, tools=_mcp_tools_v5(gateway, backend, masked, calls, call_turns, clock))
    allowed = [v4_harness._PREFIX + str(one["function"]["name"]) for one in masked   # type: ignore[index]
               if isinstance(one.get("function"), dict)]
    sid = v4_harness.session_id(run_id, case.base.id, arm, repeat)
    workdir = tempfile.mkdtemp(prefix="agentpii5-live-")
    options = v4_harness._options(case.base, model, cap, sid, {v4_harness.SERVER: server},
                                  allowed, system, workdir)

    replies: list[str] = []
    result: ResultMessage | None = None
    failed: ResultMessage | None = None
    turns = 0
    model_name = model

    async def drive() -> None:
        nonlocal result, failed, turns, model_name
        async with ClaudeSDKClient(options=options) as client:
            for index, message in enumerate(case.base.messages):
                if message.role != "user":
                    continue
                clock[0] = index
                await client.query(gateway.push_user(index))
                turn: list[str] = []
                async for reply in client.receive_response():
                    if isinstance(reply, AssistantMessage):
                        text = "".join(block.text for block in reply.content
                                       if isinstance(block, TextBlock))
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
                    gateway.note(joined)

    await asyncio.wait_for(drive(), timeout=v4_harness._timeout(case.base))
    if gateway.faults:
        raise HarnessError(f"{case.base.id}/{arm}: {gateway.faults[0]}")
    if result is None:
        raise HarnessError(f"{case.base.id}/{arm}: поток закончился без ResultMessage")
    worst = failed or result
    raw_reply = next((one for one in reversed(replies) if one.strip()), "")
    mismatch = False
    if not raw_reply:
        reply = ""
    elif case.streaming:
        reply, mismatch = stream_verdict(raw_reply, gateway.vault)
    else:
        reply = gateway.restore_text(raw_reply)
    base = ArmRun(case_id=case.base.id, arm=arm, repeat=repeat, calls=tuple(calls),
                  state=backend.snapshot(), reply=reply,
                  termination=v4_harness._termination(worst),
                  cost_usd=float(result.total_cost_usd or 0.0),
                  substitutes=substitutes_for(case.base, gateway.substitutes_seen()),
                  masked_spans=gateway.masked_spans())
    meta = ArmMeta(model=model_name, turns=turns, duration_ms=int(result.duration_ms),
                   session_id=sid, subtype=str(worst.subtype), is_error=bool(worst.is_error),
                   api_error_status=worst.api_error_status,
                   errors=tuple(str(one) for one in (worst.errors or ())), reason="", cap_usd=cap)
    run = ArmRunV5(base=base, reply_raw=raw_reply, control_reply="",
                   tool_results=gateway.tool_records(), mentions=gateway.mentions(),
                   turn_replies=restored_turn_replies(replies, gateway.restore_text),
                   call_turns=tuple(call_turns), request_count=gateway.request_index,
                   stream_mismatch=mismatch)
    return ArmOutcomeV5(v4_harness.ArmOutcome(base, meta), run)


async def _guarded_arm_v5(case: CaseV5, repeat: int, gateway: GatewayV5, backend: BackendV5,
                          model: str, cap: float, run_id: str) -> ArmOutcomeV5:
    """Never raises for one arm: v4's rule, and v4's charge for a timeout (it
    DID bill, and a ledger that books it at zero lets the next case spend money
    already gone)."""
    try:
        return await run_arm_v5(case, "I", repeat, gateway, backend, model, cap, run_id)
    except asyncio.TimeoutError:
        failed = v4_harness._failed_arm(case.base, "I", repeat, "timeout",
                                        f"таймаут {v4_harness._timeout(case.base):.0f}s",
                                        cap, cap, run_id)
    except HarnessError as broken:
        failed = v4_harness._failed_arm(case.base, "I", repeat, "harness_error",
                                        f"HarnessError: {broken}", cap, 0.0, run_id)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as broken:
        # An exception out of the masking path is the PRODUCT failing closed —
        # `gateway_5xx`, counted, never excluded.
        failed = v4_harness._failed_arm(case.base, "I", repeat, "gateway_5xx",
                                        f"{type(broken).__name__}: {broken}", cap, 0.0, run_id)
    return ArmOutcomeV5(failed, _empty_run(case, repeat))


def _empty_run(case: CaseV5, repeat: int) -> ArmRunV5:
    base = ArmRun(case_id=case.base.id, arm="I", repeat=repeat, calls=(), state=(), reply="",
                  termination="harness_error", cost_usd=0.0, substitutes={}, masked_spans={})
    return ArmRunV5(base=base, reply_raw="", control_reply="", tool_results=(), mentions=(),
                    turn_replies=(), call_turns=(), request_count=0, stream_mismatch=False)


# --- one triple ---------------------------------------------------------------------------

async def judge_triple(case: CaseV5, run: ArmRunV5, gateway: GatewayV5,
                       config: JudgeConfig | None) -> JudgeRow:
    """The residual pre-gate, then the judge — in that order, always.

    The pre-gate is deterministic and free and decides the one case the judge
    is worst at: a fake presented as the customer's own value. Asking the model
    first would pay for a verdict the gate was going to overrule.
    """
    request = judge_input(case, run)
    minted = minted_substitutes(gateway)
    refused = residual_pregate_of(request.restored_answer, minted, real_parts_of(case))
    verdict = refused if refused is not None else (
        await judge_answer(config, request, minted) if config is not None
        else JudgeVerdict(label="", reason="судья выключен (--no-judge)",
                          judged_by="none", cost_usd=0.0))
    return JudgeRow(case_id=case.base.id, repeat=run.base.repeat,
                    input_sha256=input_sha256(request, minted), verdict=verdict)


def input_sha256(request: JudgeInput, minted: tuple[str, ...]) -> str:
    """The hash of the prompt this answer was judged under — the only evidence
    on disk that a re-judged run is comparable to the previous one.

    The WHOLE prompt, not `prompt_sha256()`: two answers judged under one
    rubric are still two different measurements, and the join a re-judged run
    needs is per answer."""
    return hashlib.sha256(build_prompt(request, minted).encode("utf-8")).hexdigest()


def restored_turn_replies(raw_replies: Sequence[str],
                          restore: Callable[[str], str]) -> tuple[str, ...]:
    """Every turn's reply with the substitutes taken back out, in turn order.

    RESTORED, NOT RAW, because the judge reads these as the assistant's own
    earlier words and must never see a substitute (`contracts.ArmRunV5.
    turn_replies`, spec §5). An empty turn stays empty rather than going
    through the vault: `restore_text` on "" is work with one possible answer.

    A FUNCTION RATHER THAN A COMPREHENSION INSIDE `run_arm_v5`, for the reason
    `with_control_reply` is one: that function needs a live model and this
    claim has to be pinnable offline (`test_harness`).

    The LAST non-empty entry is the same text `raw_reply` is taken from, so it
    restores to the final answer — except on a `streaming` case, where the
    answer leg goes through `stream_verdict` and `base.reply` is the chunked
    restoration. That is why the dialogue the judge sees drops the last
    non-empty turn: the answer is evidence, with its own section, and the
    streaming leg's disagreement is `stream_mismatch`, counted apart.
    """
    return tuple(restore(text) if text.strip() else "" for text in raw_replies)


def with_control_reply(run: ArmRunV5, control_reply: str) -> ArmRunV5:
    """The C arm's reply copied onto the I arm's record.

    THE TRIPLE IS THE ONLY PLACE THAT HOLDS BOTH ARMS, so this copy happens
    here or nowhere: without it `rewrite_ratio` prints Line(0, 0) on every run
    and the gate refuses a diagnostic that could never fire
    (`contracts.ArmRunV5.control_reply`). A named function rather than a
    literal inside `run_triple_v5`, because that function needs a live model
    and this claim can then be pinned offline.
    """
    return ArmRunV5(base=run.base, reply_raw=run.reply_raw, control_reply=control_reply,
                    tool_results=run.tool_results, mentions=run.mentions,
                    turn_replies=run.turn_replies, call_turns=run.call_turns,
                    request_count=run.request_count, stream_mismatch=run.stream_mismatch)


async def run_triple_v5(case: CaseV5, repeat: int, detector: Detector,
                        ledger: v3_judge.SpendLedger, config: JudgeConfig | None,
                        model: str, run_id: str) -> TripleResult:
    """C first and alone, then I ∥ C′ — v4's order, v4's ledger discipline."""
    cap = v4_harness.cap_usd(case.base)
    triple: dict[str, object] = {
        "case_id": case.base.id, "repeat": repeat, "kind": case.base.kind,
        "behaviour": case.behaviour, "register": case.base.register,
        "cluster": case.base.cluster, "cap_usd": round(cap * 3, 6), "cost_usd": 0.0,
        "status": "refused", "reason": "", "arms": {}, "judge": {}}
    try:
        await ledger.reserve(cap * 3)
    except v3_judge.BudgetExhausted as exhausted:
        triple["reason"] = str(exhausted)
        return TripleResult([], None, (), None, triple)

    outcomes: list[v4_harness.ArmOutcome] = []
    gateway_run: ArmRunV5 | None = None
    hops: tuple[HopObservation, ...] = ()
    judged: JudgeRow | None = None
    spent = 0.0
    try:
        control = await v4_harness._guarded_arm(
            case.base, "C", repeat, PassThrough(case.base), seed_backend_v5(case), model, cap, run_id)
        outcomes.append(control)
        spent += control.run.cost_usd
        if control.run.termination in EXCLUDED_TERMINATIONS:
            triple["status"] = "excluded"
            triple["reason"] = f"C: {control.run.termination} {control.meta.reason}".strip()
            return TripleResult(outcomes, None, (), None, triple)
        gateway = GatewayV5(case, detector, Vault(":memory:", _ORG), AuditLog(":memory:"),
                            MaskCache(256))
        intervention, second = await asyncio.gather(
            _guarded_arm_v5(case, repeat, gateway, seed_backend_v5(case), model, cap, run_id),
            v4_harness._guarded_arm(case.base, "C2", repeat, PassThrough(case.base),
                                    seed_backend_v5(case), model, cap, run_id))
        outcomes.extend((intervention.base, second))
        spent += intervention.base.run.cost_usd + second.run.cost_usd
        excluded = [one.run.arm for one in outcomes if one.run.termination in EXCLUDED_TERMINATIONS]
        triple["status"] = "excluded" if excluded else "complete"
        triple["reason"] = " · ".join(
            f"{one.run.arm}: {one.meta.reason or one.run.termination}"
            for one in outcomes if one.run.termination in EXCLUDED_TERMINATIONS)
        gateway_run = with_control_reply(intervention.run, control.run.reply)
        if intervention.base.run.termination not in EXCLUDED_TERMINATIONS:
            hops = observe(case, gateway_run, None, None).hops
            judged = await judge_triple(case, gateway_run, gateway, config)
            triple["judge"] = {"label": judged.verdict.label, "judged_by": judged.verdict.judged_by,
                               "cost_usd": judged.verdict.cost_usd}
    finally:
        await ledger.settle(f"agent/{case.base.id}/{repeat}", cap * 3, spent)
        triple["cost_usd"] = round(spent, 6)
        triple["arms"] = {one.run.arm: {"termination": one.run.termination,
                                        "cost_usd": round(one.run.cost_usd, 6),
                                        "calls": len(one.run.calls), "reason": one.meta.reason}
                          for one in outcomes}
    return TripleResult(outcomes, gateway_run, hops, judged, triple)


def triple_runner(detector: Detector, ledger: v3_judge.SpendLedger, config: JudgeConfig | None,
                  model: str, run_id: str) -> TripleRunner:
    """`run_triple_v5` with the run's constants bound — the `TripleRunner`
    `drive_v5` takes."""
    async def run(case: CaseV5, repeat: int) -> TripleResult:
        return await run_triple_v5(case, repeat, detector, ledger, config, model, run_id)
    return run


# --- driving, and writing every file the report reads ---------------------------------------

async def drive_v5(cases: Sequence[CaseV5], repeats: int, run_one: TripleRunner,
                   run_dir: Path, run_id: str, concurrency: int,
                   already: frozenset[tuple[str, int]]) -> list[dict[str, object]]:
    """Every triple, written BEFORE the next one starts (v4's rule: a shell
    timeout during the next triple must not cost this one's result)."""
    limiter = asyncio.Semaphore(max(1, concurrency))
    by_id = {case.base.id: case for case in cases}
    jobs = [(case, repeat) for repeat in range(repeats) for case in cases
            if (case.base.id, repeat) not in already]
    # REPEAT FIRST, THEN COST — v4's lesson: a ceiling reached early must cost
    # REPEATS, not FAMILIES.
    jobs.sort(key=lambda job: (job[1], -v4_harness.cap_usd(job[0].base)))
    arms_sink = r.run_file(run_dir, run_id, "<run>.arms.jsonl")
    v5_sink = r.run_file(run_dir, run_id, "<run>.arms.v5.jsonl")
    hops_sink = r.run_file(run_dir, run_id, "<run>.hops.jsonl")
    judge_sink = r.run_file(run_dir, run_id, "<run>.judge.jsonl")
    triples_sink = r.run_file(run_dir, run_id, "<run>.triples.jsonl")
    triples: list[dict[str, object]] = []
    total = len(jobs)
    done = 0

    async def worker(case: CaseV5, repeat: int) -> None:
        nonlocal done
        async with limiter:
            result = await run_one(case, repeat)
            for one in result.outcomes:
                r.append_row(arms_sink, arm_record(one.run, one.meta, by_id[case.base.id].base))
            if result.gateway_run is not None:
                meta = next((one.meta for one in result.outcomes if one.run.arm == "I"), None)
                if meta is None:
                    raise HarnessError(f"{case.base.id}|{repeat}: есть запись плеча I без меты")
                r.append_row(v5_sink, r.arm_v5_record(result.gateway_run, meta, case.base))
            for hop in result.hops:
                r.append_row(hops_sink, r.hop_observation_to_json(hop))
            if result.judge is not None:
                r.append_row(judge_sink, r.judge_row_to_json(result.judge))
            r.append_row(triples_sink, result.triple)
            triples.append(result.triple)
            done += 1
            judge = dict(result.triple.get("judge") or {})       # type: ignore[arg-type]
            print(f"  [{done}/{total}] {case.base.id}|{repeat} {result.triple['status']} "
                  f"${float(result.triple['cost_usd']):.4f} хопов {len(result.hops)} "
                  f"судья={judge.get('label') or '—'}", flush=True)

    await asyncio.gather(*(worker(case, repeat) for case, repeat in jobs))
    return triples


def write_corpus(run_dir: Path, cases: Sequence[CaseV5], digest: str) -> None:
    """The two snapshots, written before the first dollar: `--report` replays
    against what was actually played, never against the tree as it is now."""
    (run_dir / "corpus.json").write_text(json.dumps(
        {"corpus": [case.base.to_json() for case in cases], "digest": digest},
        ensure_ascii=False), encoding="utf-8")
    (run_dir / "corpus.v5.json").write_text(json.dumps(
        {"corpus": [case_v5_to_json(case) for case in cases], "digest": digest},
        ensure_ascii=False), encoding="utf-8")


def stamp_judge_file(run_dir: Path, run_id: str, stamp: CalibrationStamp) -> None:
    """The calibration stamp as the FIRST row of `<run>.judge.jsonl` — where
    `report.judge_half` looks for it. Written when the run ends rather than
    when it starts: a stamp on a file with no verdicts under it would say the
    judge was calibrated for a run that never asked it anything."""
    path = r.run_file(run_dir, run_id, "<run>.judge.jsonl")
    rows = r.read_rows(path) if path.exists() else []
    rows = [row for row in rows if "calibrated" not in row]
    path.write_text("".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        for row in [r.calibration_stamp_to_json(stamp), *rows]), encoding="utf-8")


def finish_run(run_dir: Path, baseline: Path) -> list[str]:
    """The side-by-side, which writes `<run>.report.txt` and `<run>.gate.json`.

    `baseline` defaults to the run itself at the call site: the v4 block of a v5
    run IS a v4 report of v4-shaped files, so a run with no baseline still
    prints one — beside itself, which is honest and visibly useless.
    """
    return v5_report.render_side_by_side(run_dir, baseline)


# --- the ast walk that keeps this module the only importer ----------------------------------

def pseudex_importers(package_dir: Path) -> tuple[str, ...]:
    """Every module of the package whose source names `pseudex` in an import.

    Parsed with `ast`, not grepped: a grep counts the word inside a docstring
    and this file's docstring names it four times.
    """
    found: list[str] = []
    for path in sorted(package_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "pseudex" or name.startswith("pseudex.") for name in names):
                found.append(path.stem)
                break
    return tuple(found)


# --- CLI -------------------------------------------------------------------------------------

def _load_corpus(path: Path) -> tuple[list[CaseV5], str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases = [case_v5_from_json(one) for one in raw["corpus"]]
    return cases, str(raw.get("digest") or corpus_digest_v5(cases))


def _ladder(path: Path) -> Ladder:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Ladder(version=int(raw["version"]), seed=int(raw["seed"]),
                  corpus_sha256=str(raw["corpus_sha256"]),
                  tiers={name: tuple(ids) for name, ids in dict(raw["tiers"]).items()})


def _resume(source: Path) -> tuple[frozenset[tuple[str, int]], float]:
    """Triples already finished CLEANLY in that directory: kept, and their cost
    charged against the ceiling so it bounds the WHOLE measurement."""
    already: set[tuple[str, int]] = set()
    spent = 0.0
    for triples_file in sorted(source.glob("*.triples.jsonl")):
        arms_file = triples_file.with_name(triples_file.name.replace(".triples.jsonl", ".arms.jsonl"))
        if not arms_file.exists():
            continue
        by_key: dict[tuple[str, int], dict[str, str]] = {}
        for row in r.read_rows(arms_file):
            key = (str(row["case_id"]), int(row["repeat"]))       # type: ignore[arg-type]
            by_key.setdefault(key, {})[str(row["arm"])] = str(row.get("termination"))
        for triple in r.read_rows(triples_file):
            key = (str(triple["case_id"]), int(triple["repeat"]))  # type: ignore[arg-type]
            arms = by_key.get(key, {})
            if key in already or set(arms) != set(ARMS):
                continue
            if any(value != "done" for value in arms.values()):
                continue
            already.add(key)
            spent += float(triple.get("cost_usd") or 0.0)
    return frozenset(already), spent


def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", nargs="?", default=str(here / "corpus.v5.json"))
    parser.add_argument("--ladder", default=str(here / "ladder.json"))
    parser.add_argument("--tier", default="nano",
                        choices=("nano", "small", "medium", "large", "holdout", "max"))
    parser.add_argument("--ids", default="", help="запятые: точный список случаев вместо яруса")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--ceiling", type=float, default=12.0, help="потолок на прогон, USD")
    parser.add_argument("--model", default=AGENT_MODEL)
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--out", default="")
    parser.add_argument("--report", default="", help="пересобрать отчёт из файлов: без модели и без трат")
    parser.add_argument("--resume", default="", help="каталог прерванного прогона")
    parser.add_argument("--baseline", default="", help="каталог прогона v4 для колонки сравнения")
    args = parser.parse_args()

    if args.report:
        run_dir = Path(args.report)
        baseline = Path(args.baseline) if args.baseline else run_dir
        for line in finish_run(run_dir, baseline):
            print(line)
        return 0

    everything, digest = _load_corpus(Path(args.corpus))
    by_id = {case.base.id: case for case in everything}
    if args.ids:
        wanted = [one.strip() for one in args.ids.split(",") if one.strip()]
        missing = [one for one in wanted if one not in by_id]
        if missing:
            print(f"нет таких случаев: {missing}", file=sys.stderr)
            return 2
        cases = [by_id[one] for one in wanted]
        tier_name = "ids"
    else:
        picked = {one.id for one in tier([case.base for case in everything],
                                         _ladder(Path(args.ladder)), args.tier)}
        cases = [case for case in everything if case.base.id in picked]
        tier_name = args.tier
    if not cases:
        print("выборка пуста", file=sys.stderr)
        return 2

    load_dev_bundle()
    detector = Detector()
    run_id = str(uuid.uuid4())
    out = Path(args.out) if args.out else (here.parent / "runs" / datetime.now().strftime("%Y-%m-%d")
                                           / f"v5-live-{tier_name}")
    out.mkdir(parents=True, exist_ok=True)
    write_corpus(out, cases, digest)
    already, resumed = _resume(Path(args.resume)) if args.resume else (frozenset(), 0.0)
    if args.resume:
        print(f"продолжение: взято {len(already)} готовых троек на ${resumed:.2f}", flush=True)

    # ONE LEDGER for the agent and the judge, `committed + reserved <= ceiling`
    # at every instant. The judge's config holds the SAME object, which is what
    # `test_harness.test_ledger_shared` asserts.
    ledger = v3_judge.SpendLedger(r.run_file(out, run_id, "<run>.spend.tsv"),
                                  max(0.0, args.ceiling - resumed))
    config = None if args.no_judge else JudgeConfig(
        model=args.judge_model, ledger=ledger, query_cap_usd=QUERY_CAP_USD, retries=RETRIES,
        trace_path=out / f"{run_id}.judge.trace.jsonl")
    print(f"прогон {run_id} · агент {args.model} · судья "
          f"{'—' if args.no_judge else args.judge_model} · промпт {prompt_sha256()[:12]} · "
          f"{len(cases)} случаев × K={args.repeats} × 3 плеча · потолок ${args.ceiling:.2f}",
          flush=True)
    started = time.time()
    triples = asyncio.run(drive_v5(cases, args.repeats,
                                   triple_runner(detector, ledger, config, args.model, run_id),
                                   out, run_id, args.concurrency, already))
    spent = sum(float(one["cost_usd"]) for one in triples)
    print(f"\nпотрачено ${spent:.2f} из ${args.ceiling:.2f} за {time.time() - started:.0f}s")
    # НЕ ОТКАЛИБРОВАН until a calibration file says otherwise: silence about
    # the judge is «неизвестно», never «годен».
    stamp_judge_file(out, run_id, CalibrationStamp(
        judge_model="" if args.no_judge else args.judge_model, prompt_sha256=prompt_sha256(),
        n=0, raw_agreement=0.0, kappa=0.0, per_type_kappa={}, repeat_disagreement=1.0,
        calibrated=False))
    (out / f"{run_id}.meta.json").write_text(json.dumps(
        {"run_id": run_id, "benchmark": "agentpii5", "model": args.model,
         "judge_model": "" if args.no_judge else args.judge_model, "tier": tier_name,
         "repeats": args.repeats, "digest": digest, "ceiling_usd": args.ceiling,
         "spent_usd": round(spent, 6), "prompt_sha256": prompt_sha256(),
         "finished": datetime.now(timezone.utc).isoformat()},
        ensure_ascii=False, indent=2), encoding="utf-8")
    for line in finish_run(out, Path(args.baseline) if args.baseline else out):
        print(line)
    print(f"\nкаталог прогона: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
