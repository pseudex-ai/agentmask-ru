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
restored twice: chunk by chunk through `pseudex.redact.StreamDetokenizer` in
17-character pieces — a prime, so no boundary can align with a token by luck —
and whole (`unmask_text`). **THE CHUNKED ONE IS WHAT IS SCORED** (F3.1,
superseding ruling R-46): it is the text the streaming customer actually reads,
and scoring the whole-text restoration printed the product correct on an answer
the customer read wrong. On the corpus's own streaming replies the two really
do disagree (3.4% in the reviewers' fuzz — the whole-text leg swallowed the
generic word «улицу»), and that difference is `stream_mismatch`: a defect of
the streaming leg, counted apart and never folded into the form lines
(spec §3.7).
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
from dataclasses import dataclass, replace
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
from bench.agentpii5.calibration import write_stamp
from bench.agentpii5.contracts import (
    AGENT_MODEL, ECHO_TAG_PREFIX, JUDGE_MODEL, QUERY_CAP_USD, RETRIES, ArmRunV5,
    CalibrationStamp, CaseV5, HopObservation, JudgeRow, JudgeVerdict,
    MentionRecord, ToolResultRecord)
from bench.agentpii5.judge import (
    JUDGE_TEMPERATURE, JudgeConfig, LeakedPrompt, OracleLeak, build_prompt, judge_input,
    judge_prompt, masked_dialogue, prompt_sha256, residual_pregate_of)
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


def stream_verdict(raw: str, vault: Vault) -> tuple[str, str, bool]:
    """(chunked restoration, whole-text restoration, do they differ).

    THE CHUNKED ONE COMES FIRST BECAUSE IT IS THE ANSWER. A streaming customer
    reads `delta.content` as it arrives, and the sidecar restores it through
    the chunk contract; the whole-text restoration is a diagnostic of ours that
    nobody outside this benchmark ever sees. Scoring the diagnostic instead of
    the answer is how 84 cases were graded on text that was never delivered.
    """
    whole = unmask_text(raw, vault)
    chunked = restore_stream(raw, vault, STREAM_CHUNK)
    return chunked, whole, chunked != whole


@dataclass(frozen=True)
class AnswerLeg:
    """What one restoration of the final reply produced.

    THREE VALUES RATHER THAN TWO, because `reply_whole` used to be computed
    here and dropped on the floor (R-54): `stream_fidelity` says THAT the two
    restorations disagreed, and a reader who then asks WHICH TEXT the customer
    lost had nothing on disk to look at — the whole-text leg was restored a
    second time, for a `len()` in a log line, and never kept.

    `reply` is what the run SCORES, `reply_whole` is the whole-text
    restoration of a streaming reply ("" on an ordinary case, where the two
    restorations are one string and keeping it twice would invite a reader to
    compare a field with itself), `mismatch` is `ArmRunV5.stream_mismatch`.
    """

    reply: str
    reply_whole: str
    mismatch: bool


def answer_leg(raw_reply: str, streaming: bool, vault: Vault,
               restore: Callable[[str], str]) -> AnswerLeg:
    """The restored answer the run SCORES, the diagnostic beside it, and the
    streaming leg's verdict.

    ONE function for the choice, and a function rather than four lines inside
    `run_arm_v5`, for the reason `with_control_reply` is one: the choice lives
    inside a coroutine that needs a live model, and a claim only a paid run can
    check is a claim nobody checks (`test_harness_stream` drives this one over
    the corpus's own streaming cases).

    `restore` is the gateway's whole-text restorer for an ordinary case; a
    streaming case never uses it, because there the customer's text is the
    chunked one.
    """
    if not raw_reply:
        return AnswerLeg(reply="", reply_whole="", mismatch=False)
    if not streaming:
        return AnswerLeg(reply=restore(raw_reply), reply_whole="", mismatch=False)
    chunked, whole, mismatch = stream_verdict(raw_reply, vault)
    return AnswerLeg(reply=chunked, reply_whole=whole, mismatch=mismatch)


def with_streamed_answer(turns: tuple[str, ...], answer: str) -> tuple[str, ...]:
    """The last spoken turn replaced by what the STREAMING customer read.

    `restored_turn_replies` restores every turn whole, which is right for the
    intermediate ones (they were not streamed to anyone by this harness) and
    wrong for the final one: `observe`'s answer leg, the judge's evidence and
    the report all read the answer, and two spellings of it in one record is a
    number nobody can reproduce. A run whose agent said nothing keeps its empty
    tuple — there is no turn to replace and inventing one would fabricate a
    reply.
    """
    spoken = [position for position, text in enumerate(turns) if text.strip()]
    if not spoken:
        return turns
    return tuple(answer if position == spoken[-1] else text
                 for position, text in enumerate(turns))


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
    leg = answer_leg(raw_reply, case.streaming, gateway.vault, gateway.restore_text)
    reply = leg.reply
    if leg.mismatch:
        # NAMED ON THE RUN LOG, not only counted: `stream_mismatch` says THAT
        # the two restorations disagreed; the run log says WHICH case, so an
        # operator can ask for the two texts. The lengths, never the values —
        # a restored answer is the customer's own data and the console of a
        # 1 594-case run is not the place for it. The lengths come off the ONE
        # restoration `answer_leg` already did: restoring the reply a third
        # time for a log line is how the two numbers in one message could come
        # from two different restorations.
        print(f"  СТРИМ РАЗОШЁЛСЯ {case.base.id}|{repeat}: клиент прочитал "
              f"{len(reply)} знаков, целиком восстановилось "
              f"{len(leg.reply_whole)}", file=sys.stderr, flush=True)
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
    turn_replies = restored_turn_replies(replies, gateway.restore_text)
    if case.streaming and reply:
        turn_replies = with_streamed_answer(turn_replies, reply)
    run = ArmRunV5(base=base, reply_raw=raw_reply, control_reply="",
                   tool_results=gateway.tool_records(), mentions=gateway.mentions(),
                   turn_replies=turn_replies,
                   call_turns=tuple(call_turns), request_count=gateway.request_index,
                   stream_mismatch=leg.mismatch, reply_whole=leg.reply_whole,
                   # NOT KNOWN YET, and zero here is the honest placeholder: how
                   # many earlier turns still carried a substitute is decided
                   # when the judge's prompt is built, three arms later, and
                   # `run_triple_v5` lays it over this record with
                   # `with_turn_residual`. Guessing it here would mean masking
                   # the dialogue twice, once for a number and once for the
                   # judge, and two spellings of one scan is how they drift.
                   turn_residual=0)
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
                    turn_replies=(), call_turns=(), request_count=0, stream_mismatch=False,
                    reply_whole="", turn_residual=0)


# --- one triple ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JudgeOutcome:
    """The judge's row plus what building its prompt revealed.

    `turn_residual` is how many of the agent's EARLIER turns still carried a
    minted substitute when the prompt was built — the same defect `residual`
    counts in the answer, one turn sooner. It travels beside the row rather
    than inside it because `JudgeRow` is normative (R-02) and belongs to
    another owner; `run_triple_v5` lays it onto the I arm's record
    (`with_turn_residual`) and onto the triple row (`triple_totals`), which is
    where the metric and the report read it (R-54).
    """

    row: JudgeRow
    turn_residual: int


async def judge_triple(case: CaseV5, run: ArmRunV5, gateway: GatewayV5,
                       config: JudgeConfig | None) -> JudgeOutcome:
    """The residual pre-gate, then the judge — in that order, always.

    The pre-gate is deterministic and free and decides the one case the judge
    is worst at: a fake presented as the customer's own value. Asking the model
    first would pay for a verdict the gate was going to overrule.

    THE PROMPT IS BUILT ONCE, here, and for two readers: the model is sent it
    and `input_sha256` hashes it. It used to be built a second time for the
    hash, AFTER the pre-gate had already decided the case — so a case the judge
    was never going to be asked about still paid the build and, when a
    substitute stood in an earlier turn, still raised out of it.
    """
    request = judge_input(case, run)
    minted = minted_substitutes(gateway)
    _, turn_residual = masked_dialogue(request, minted)
    try:
        prompt = build_prompt(request, minted)
    except OracleLeak as leak:
        # THE COUNT SURVIVES THE LEAK (R-54). What `build_prompt` still refuses
        # is a substitute in the QUESTION or the ORACLE — ours, and worth
        # stopping the judging over — but the dialogue has already been read by
        # then, so how many earlier turns carried a substitute is KNOWN. Losing
        # it with the stack frame made the leaked triple's row say «0», which
        # cannot be told from «no earlier turn held one».
        raise LeakedPrompt(str(leak), turn_residual) from leak
    refused = residual_pregate_of(request.restored_answer, minted, real_parts_of(case))
    verdict = refused if refused is not None else (
        await judge_prompt(config, request, prompt) if config is not None
        else JudgeVerdict(label="", reason="судья выключен (--no-judge)",
                          judged_by="none", cost_usd=0.0))
    return JudgeOutcome(
        row=JudgeRow(case_id=case.base.id, repeat=run.base.repeat,
                     input_sha256=input_sha256(prompt), verdict=verdict),
        turn_residual=turn_residual)


def input_sha256(prompt: str) -> str:
    """The hash of the prompt this answer was judged under — the only evidence
    on disk that a re-judged run is comparable to the previous one.

    THE PROMPT, not `prompt_sha256()`: two answers judged under one rubric are
    still two different measurements, and the join a re-judged run needs is per
    answer. Takes the built string rather than (request, minted), so what is
    hashed is what was sent and not a second build of it.
    """
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


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
    restores to the final answer. On a `streaming` case `run_arm_v5` then lays
    the CHUNKED restoration over that entry (`with_streamed_answer`), because
    the whole-text restoration of the final turn is a text nobody was served
    and the record must hold one answer, not two. The dialogue the judge sees
    drops the last non-empty turn either way: the answer is evidence and has
    its own section.
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
    # `replace`, NOT a field-by-field rebuild. The rebuild was here, and when
    # `ArmRunV5` grew `reply_whole` and `turn_residual` (R-54) it did not drop
    # them loudly — it dropped them by not mentioning them, which is the defect
    # class this benchmark exists to refuse. `replace` carries every field the
    # record has and fails on a field it does not.
    return replace(run, control_reply=control_reply)


def with_turn_residual(run: ArmRunV5, turn_residual: int) -> ArmRunV5:
    """How many earlier turns still carried a substitute, laid onto the record.

    THE NUMBER IS KNOWN THREE ARMS LATE. `masked_dialogue` counts it while the
    judge's prompt is built, long after `run_arm_v5` has finished — so it
    cannot be a field the arm sets, and it lived on the triple row instead,
    where `residual` (a per-observation metric that reads `ArmRunV5`) could not
    reach it: a substitute the customer read in turn 2 and not in the final
    answer was counted by nothing (R-54).

    A named function rather than a literal inside `run_triple_v5`, for the
    reason `with_control_reply` is one: that function needs a live model, and a
    claim only a paid run can check is a claim nobody checks.
    """
    if turn_residual < 0:
        raise HarnessError(f"{run.base.case_id}|{run.base.repeat}: нераскрытых подмен в ходах "
                           f"{turn_residual} — отрицательным это число не бывает")
    return replace(run, turn_residual=turn_residual)


async def run_triple_v5(case: CaseV5, repeat: int, detector: Detector,
                        ledger: v3_judge.SpendLedger, config: JudgeConfig | None,
                        model: str, run_id: str) -> TripleResult:
    """C first and alone, then I ∥ C′ — v4's order, v4's ledger discipline."""
    cap = v4_harness.cap_usd(case.base)
    triple: dict[str, object] = {
        "case_id": case.base.id, "repeat": repeat, "kind": case.base.kind,
        "behaviour": case.behaviour, "register": case.base.register,
        "cluster": case.base.cluster, "cap_usd": round(cap * 3, 6), "cost_usd": 0.0,
        # The judge spends from the SAME ledger as the arms, so a resumed run
        # that charged only the arms against its ceiling under-counted what the
        # measurement had already cost (`_resume` reads `cost_usd`). Both
        # numbers are written: the total is what bounds the run, the judge's
        # own share is what the report prints on its cost line (F2.4). Through
        # records' OWN writer (R-54), because the report reads them through
        # records' reader and a row spelled here by hand is a second schema.
        **r.triple_totals_to_json(triple_totals(None, 0)),
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
    turn_residual = 0
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
            try:
                outcome = await judge_triple(case, gateway_run, gateway, config)
            except LeakedPrompt as leak:
                # A LEAK IS RECORDED, NEVER A REASON TO THROW AWAY THREE PAID
                # ARMS. `masked_dialogue` has removed the reachable half of this
                # (a substitute standing in an earlier turn); what is left is a
                # substitute in the QUESTION or the ORACLE, which is ours and
                # is worth stopping the triple over — but not the run. The
                # verdict is `none`, so it counts nowhere, the reason names the
                # leak on disk instead of in a traceback nobody kept, and the
                # turn count the build had already measured rides on the
                # exception (`LeakedPrompt`) rather than being replaced by a
                # zero nobody can tell from silence.
                print(f"[judge] {case.base.id}|{repeat}: {leak}", file=sys.stderr, flush=True)
                outcome = JudgeOutcome(
                    row=JudgeRow(case_id=case.base.id, repeat=repeat, input_sha256="",
                                 verdict=JudgeVerdict(label="", reason=f"OracleLeak: {leak}",
                                                      judged_by="none", cost_usd=0.0)),
                    turn_residual=leak.turn_residual)
            judged = outcome.row
            turn_residual = outcome.turn_residual
            # THE RECORD, NOT ONLY THE ROW (R-54): `residual` is a
            # per-observation metric and reads `ArmRunV5`, so a count that
            # lived on the triple row alone was a count no line could reach.
            gateway_run = with_turn_residual(gateway_run, turn_residual)
            triple["judge"] = {"label": judged.verdict.label, "judged_by": judged.verdict.judged_by,
                               "cost_usd": judged.verdict.cost_usd}
    finally:
        await ledger.settle(f"agent/{case.base.id}/{repeat}", cap * 3, spent)
        # ONE PLACE COMPUTES THE JUDGE'S SHARE, and both readers take it from
        # there: the triple's own `judge_cost_usd` column and the `cost_usd`
        # that bounds a resumed run. They were two expressions over the same
        # verdict, which is how a rounding of one and not the other becomes a
        # ceiling nobody can reconcile.
        totals = triple_totals(judged, turn_residual)
        triple.update(r.triple_totals_to_json(totals))
        triple["cost_usd"] = charged(spent, totals.judge_cost_usd)
        triple["arms"] = {one.run.arm: {"termination": one.run.termination,
                                        "cost_usd": round(one.run.cost_usd, 6),
                                        "calls": len(one.run.calls), "reason": one.meta.reason}
                          for one in outcomes}
    return TripleResult(outcomes, gateway_run, hops, judged, triple)


def triple_totals(judged: JudgeRow | None, turn_residual: int) -> r.TripleTotals:
    """The two numbers a triple row carries beyond v4's own — from the verdict
    itself, in one place.

    `judge_cost_usd` is the sum of what THIS triple's judging cost, and a
    triple holds exactly one verdict (`<run>.judge.jsonl` is keyed by (case,
    repeat) — a second row under one key is lost by its own reader), so the
    sum is that verdict's `cost_usd` and never a second tally kept beside it.
    A triple whose judge never ran (`--no-judge`, a refused reservation, a
    control that excluded the triple before the I arm) spent nothing, which is
    a measured zero and not an absent field: `records.triple_totals_from_json`
    refuses the row where the key is missing.
    """
    return r.TripleTotals(judge_cost_usd=0.0 if judged is None else judged.verdict.cost_usd,
                          turn_residual=turn_residual)


def charged(arms_usd: float, judge_usd: float) -> float:
    """What one triple charged the run's ceiling: the arms AND the judge.

    The judge reserves from the SAME ledger as the arms, so a `cost_usd` that
    counted only the arms let `--resume` re-open a ceiling the measurement had
    already spent — the run would then buy the difference twice. A named
    function because that is the claim `test_harness` pins, and it rounds where
    the ledger rounds so the file and the ledger cannot disagree by a cent.
    """
    return round(arms_usd + judge_usd, 6)


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


BENCHMARK: str = "agentpii5"


def write_meta(run_dir: Path, run_id: str, model: str, judge_model: str, tier: str,
               repeats: int, digest: str, ceiling_usd: float, spent_usd: float) -> Path:
    """What the run itself was (`RUN_FILES["<run>.meta.json"]`, F1.22).

    A NAMED WRITER rather than a literal inside `main`, for the reason
    `stamp_judge_file` is one: the report needs two of these fields and can get
    them nowhere else — the CEILING the run was given (a cost line without it
    says «spent $12 of an unknown ceiling») and the `prompt_sha256` a
    calibration stamp must match — and a file written only by a paid run is a
    file whose absence no test can notice.

    `benchmark`, the prompt hash and the finish time are NOT parameters: they
    are facts about the process that is writing, and a caller allowed to pass
    the hash could stamp a run with the hash of another rubric — which is the
    one thing the field exists to prevent.
    """
    path = r.run_file(run_dir, run_id, "<run>.meta.json")
    path.write_text(json.dumps(
        {"run_id": run_id, "benchmark": BENCHMARK, "model": model,
         "judge_model": judge_model, "tier": tier, "repeats": repeats, "digest": digest,
         "ceiling_usd": ceiling_usd, "spent_usd": round(spent_usd, 6),
         "prompt_sha256": prompt_sha256(),
         "finished": datetime.now(timezone.utc).isoformat()},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def stamp_judge_file(run_dir: Path, run_id: str, stamp: CalibrationStamp) -> None:
    """The calibration stamp as the FIRST row of `<run>.judge.jsonl` — where
    `report.judge_half` looks for it. Written when the run ends rather than
    when it starts: a stamp on a file with no verdicts under it would say the
    judge was calibrated for a run that never asked it anything.

    The writing itself is `calibration.write_stamp`, because the other caller
    (`calibration import --run`, which stamps the numbers a filled sheet
    produced) must write the SAME row 0 — and a report refuses to print
    without it, so two spellings of it would be two ways to be
    «НЕ ОТКАЛИБРОВАН» for different reasons.
    """
    write_stamp(run_dir, run_id, stamp)


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
    # THE TEMPERATURE IS NAMED, NOT INHERITED (R-56). It is the module constant
    # rather than a flag, because `calibration export --repeats K` is a second
    # process and «the repeats run at the same temperature as the run» can only
    # hold by construction — a flag is a value a human retypes, and a judge
    # calibrated at one temperature certifies an instrument that ran at another.
    config = None if args.no_judge else JudgeConfig(
        model=args.judge_model, ledger=ledger, query_cap_usd=QUERY_CAP_USD, retries=RETRIES,
        trace_path=out / f"{run_id}.judge.trace.jsonl", temperature=JUDGE_TEMPERATURE)
    print(f"прогон {run_id} · агент {args.model} · судья "
          f"{'—' if args.no_judge else args.judge_model} (t={JUDGE_TEMPERATURE}) · "
          f"промпт {prompt_sha256()[:12]} · "
          f"{len(cases)} случаев × K={args.repeats} × 3 плеча · потолок ${args.ceiling:.2f}",
          flush=True)
    started = time.time()
    triples = asyncio.run(drive_v5(cases, args.repeats,
                                   triple_runner(detector, ledger, config, args.model, run_id),
                                   out, run_id, args.concurrency, already))
    spent = sum(float(one["cost_usd"]) for one in triples)
    # THROUGH RECORDS' READER, never `row.get(key) or 0` (R-54): that spelling
    # reads a triple written by an older harness — one that recorded no judge
    # share at all — as a run with a free judge, and the two readings are
    # indistinguishable in the printed line.
    totals = [r.triple_totals_from_json(one) for one in triples]
    judged = sum(one.judge_cost_usd for one in totals)
    residual_turns = sum(one.turn_residual for one in totals)
    # THE JUDGE'S SHARE ON ITS OWN LINE: it draws on the same ledger as the
    # arms, so a header that printed one number invited the reading «the agent
    # cost all of this». `turn_residual` is beside it because a substitute the
    # customer read in an earlier turn is the same defect as one in the answer,
    # and the operator is owed the count before the report is built.
    print(f"\nпотрачено ${spent:.2f} из ${args.ceiling:.2f} "
          f"(судья ${judged:.2f}) за {time.time() - started:.0f}s · "
          f"нераскрытых подмен в ходах: {residual_turns}")
    # НЕ ОТКАЛИБРОВАН until a calibration file says otherwise: silence about
    # the judge is «неизвестно», never «годен».
    stamp_judge_file(out, run_id, CalibrationStamp(
        judge_model="" if args.no_judge else args.judge_model, prompt_sha256=prompt_sha256(),
        n=0, raw_agreement=0.0, kappa=0.0, per_type_kappa={}, repeat_disagreement=1.0,
        calibrated=False))
    write_meta(out, run_id, model=args.model,
               judge_model="" if args.no_judge else args.judge_model, tier=tier_name,
               repeats=args.repeats, digest=digest, ceiling_usd=args.ceiling, spent_usd=spent)
    for line in finish_run(out, Path(args.baseline) if args.baseline else out):
        print(line)
    print(f"\nкаталог прогона: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
