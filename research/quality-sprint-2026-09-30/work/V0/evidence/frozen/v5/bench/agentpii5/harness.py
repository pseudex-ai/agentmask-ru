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
import os
import random
import sys
import tempfile
import time
import traceback
import uuid
from collections.abc import Awaitable, Callable, Sequence
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
from bench.agentpii4.schema import ARMS, EXCLUDED_TERMINATIONS, Case, Ladder, PiiItem, tier
from bench.agentpii4.writer import WriterError
from bench.agentpii5 import build as corpus_build
from bench.agentpii5 import provider
from bench.agentpii5 import records as r
from bench.agentpii5 import report as v5_report
from bench.agentpii5 import reportjson
from bench.agentpii5 import runinfo
from bench.agentpii5.codex_connector import CodexJudgeConnector, CodexSettings
from bench.agentpii5.connectors import (
    AgentConnector, Json, ToolResult, ToolSpec, json_object)
from bench.agentpii5.deepseek_connector import DeepSeekConnector, DeepSeekSettings
from bench.agentpii5.calibration import write_stamp
from bench.agentpii5.contracts import (
    AGENT_MODEL, BENCHMARK, ECHO_TAG_PREFIX, JUDGE_MODEL, QUERY_CAP_USD, RETRIES, ArmRunV5,
    CalibrationStamp, CaseV5, HopObservation, JudgeRow, JudgeVerdict,
    MentionRecord, ModelResponse, ModelTrace, ToolResultRecord)
from bench.agentpii5.judge import (
    JUDGE_TEMPERATURE, ConnectedJudgeConfig, JudgeConfig, LeakedPrompt, OracleLeak, build_prompt, judge_input,
    judge_prompt, masked_dialogue, prompt_sha256, residual_pregate_of)
from bench.agentpii5.mock import BackendV5, seed_backend_v5
from bench.agentpii5 import payload_canaries as canaries
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
# ЧЕРЕЗ ЧТО ЭТОТ ФАЙЛ НА САМОМ ДЕЛЕ ЗОВЁТ МОДЕЛЬ. `claude_agent_sdk` говорит с
# Anthropic; `provider.py` знает три провайдера, и пока плечо не ходит через
# `provider.call_model`, любой другой — это запись о модели, которая не
# отвечала. Константа названа здесь, рядом с импортом SDK, а не в `provider`:
# провайдер — свойство ЭТОГО пути к модели, а не таблицы провайдеров.
SDK_PROVIDER: str = "anthropic"
# What a triple's row says when the run's ceiling refused the judge's call. A
# constant, because three readers must say the same words: the verdict's
# `reason` in `<run>.judge.jsonl`, the `judge.reason` of the triple row, and
# `test_harness`'s check that the arms survived it.
JUDGE_SKIPPED_BUDGET: str = "судья пропущен (потолок)"
# A PRIME, so no chunk boundary can align with a token, a separator or a word
# by construction. 16 would split «+7 900 000-00-00» the same way on every
# phone in the corpus and a carry bug would hide behind the regularity.
STREAM_CHUNK: int = 17
# THE PER-CONVERSATION TOOL-CALL BUDGET. A long `sequential_chain` case makes
# more calls than `3 * len(user turns) + 10` — search → read → write, with the
# model's own retries and parallel calls on top — and that hardcoded floor was
# excluding honest chains as `ConnectorLimit("tool call limit reached")`. The
# guard must sit far above any honest chain, while `--agent-turn-limit` (the
# request count) and the per-case timeout still bound a stuck model.
DEFAULT_MAX_CALLS: int = 4096


# DeepSeek rejects `max_tokens` above this ("the valid range of max_tokens is
# [1, 393216]"), so the per-response cap must stay inside it even when the
# operator asked for a larger session budget.
DEEPSEEK_MAX_OUTPUT_TOKENS = 393216


def deepseek_max_output_tokens(connector_max_tokens: int) -> int:
    """The per-response output cap: the session token budget, NOT a fraction of it.

    `max_tokens` bounds the cumulative SESSION — input plus output across every
    request of one conversation (`deepseek_connector.py` checks it after each
    response). `max_output_tokens` bounds ONE response's output. The old
    `min(16000, …)` floor cut long mail chains short mid-answer
    (`DeepSeek response ended incomplete`); one response may legitimately grow to
    the session budget while the session check still holds the whole conversation
    to it.
    """
    return min(connector_max_tokens, DEEPSEEK_MAX_OUTPUT_TOKENS)


def scaled_timeout(case: Case, scale: float) -> float:
    """v4's per-case timeout, scaled by `--timeout-scale`.

    v5 calls `v4_harness._timeout(case)` in THREE places — `converse(...,
    timeout_s=...)`, `asyncio.wait_for(drive(), timeout=...)` and the `timeout`
    arm's reason — and the three must multiply by the SAME scale, or a run's
    record and its actual deadline disagree about how long the model had. v4's
    own `_timeout` stays untouched: it is the baseline the treatment arm is
    measured against, and the control arms still run under it.
    """
    return v4_harness._timeout(case) * scale


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
    # S02 CAPTURE: what the gateway handed each boundary, per (case, repeat), so
    # `drive_v5` can persist it. Empty for a triple that never reached the
    # intervention arm (a budget refusal, an excluded C), and empty for a caller
    # that built a `TripleResult` by hand — a canned row honestly measures
    # nothing, which is what NOT_MEASURED says.
    captures: tuple[canaries.RunCapture, ...] = ()


class TripleRunner(Protocol):
    """What `drive_v5` calls per (case, repeat).

    An explicit parameter rather than a module attribute a test monkeypatches:
    `test_harness.test_run_files_written` must drive the WRITER with canned
    arms, and a seam that exists only under a test is a seam nobody looked at.
    """

    async def __call__(self, case: CaseV5, repeat: int) -> TripleResult: ...


# --- the gateway that also remembers ----------------------------------------------------

def _declared_surfaces(case: CaseV5, item: PiiItem) -> tuple[str, ...]:
    """Original literals the case declared before the gateway processed it."""
    out: list[str] = [item.value, item.canonical]
    where = item.where
    if where.kind == "message" and 0 <= where.msg < len(case.base.messages):
        content = case.base.messages[where.msg].content
        out.append(content[where.start:where.end])
    return tuple(dict.fromkeys(value for value in out if value))


def _manifest_at_delivery(case: CaseV5, manifest: canaries.CanaryManifest,
                          boundary: str, original: str) -> canaries.CanaryManifest:
    """Place case-declared literals using the raw payload before masking output.

    The detector, replacement spans and delivered bytes never select a canary.
    A declared ordinary value selects a neighbour on the same boundary.
    """
    if not original:
        return manifest
    specs = list(manifest.canaries)
    positions = {one.id: index for index, one in enumerate(specs)}
    context = {"tool_result": "result", "tool_error": "error",
               "tool_args": "argument", "final_answer": "answer",
               "model_request": "request"}.get(boundary, "message")
    for item in case.base.pii:
        planted = tuple(canaries.PlantedSurface(value, canaries.SURFACE_FULL)
                        for value in _declared_surfaces(case, item)
                        if canaries.surface_in(original, value))
        if not planted:
            continue
        canary_id = f"{item.id}@{boundary}"
        if canary_id in positions:
            index = positions[canary_id]
            specs[index] = replace(specs[index], surfaces=tuple(dict.fromkeys(
                specs[index].surfaces + planted)))
        else:
            positions[canary_id] = len(specs)
            specs.append(canaries.CanarySpec(canary_id, item.type, boundary,
                                             planted, "", context))
    neighbours = list(manifest.neighbours)
    present = {(one.boundary, one.text) for one in neighbours}
    for ordinary in (*case.base.plain, *case.base.negatives):
        value = ordinary.value
        key = (boundary, value)
        if value and key not in present and canaries.surface_in(original, value):
            neighbours.append(canaries.Neighbour(boundary, value))
            present.add(key)
    return replace(manifest, canaries=tuple(specs), neighbours=tuple(neighbours))

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
                 cache: MaskCache, capture: bool = False,
                 manifest: canaries.CanaryManifest | None = None) -> None:
        super().__init__(case.base, detector, vault, audit, cache)
        # ВОССТАНАВЛИВАЕМ ТЕМ ЖЕ VIEW, КОТОРЫМ МАСКИРОВАЛИ (G3.1). v4 masks
        # through `_view` (`MaskContext(vault=self._view)`) and restores through
        # `_base`; production restores through the view too
        # (`service._scoped` → `vault.for_conversation(conversation_id)`), and a
        # LINKED row is written under a CONVERSATION-scoped canonical
        # (CLAUDE.md «The conversation scope»), so the base vault cannot resolve
        # it. Measured on this corpus through `testkit.load_dev_bundle()`: 548
        # of 1260 minted substitutes restore differently through the two
        # objects and 458 the base vault leaves STANDING — a fake reaching the
        # tool, an answer the pre-gate calls «неверно», and every value metric
        # of the gateway arm scoring a restoration production never performs.
        #
        # The ONE attribute every v4 restorer reads is rebound, rather than
        # `vault` / `restore_text` / `restore_arguments` being overridden here:
        # a copy of `restore_arguments`'s body (the JSON walk, `residual_tokens`,
        # the piece fallback) would drift from v4's the first time v4 changed
        # it, and v5 never edits v4. The object is the SAME `_view` the masking
        # used — obtained once per conversation, never a second
        # `for_conversation` call, which would be a second scope to keep equal.
        self._base = self._view
        self._case5 = case
        self._requests = 0
        self._mentions: list[MentionRecord] = []
        self._results: list[ToolResultRecord] = []
        # PAYLOAD CANARIES (S02). Off by default: a run that does not ask for
        # the capture pays nothing. The composed request is taken from the
        # production mask call itself; no second mask pass is needed.
        # Candidate literals and ordinary neighbours come from the case. Their
        # boundary placement is recorded from each raw payload at delivery.
        self._capture = capture
        self._auto_manifest = capture and manifest is None
        self._manifest = (manifest if manifest is not None else
                          canaries.CanaryManifest(canaries=(), source="case-construction")
                          if capture else None)
        self._payloads: list[canaries.CapturedPayload] = []

    # --- the exact bytes this gateway delivered, at the moment it delivered them ------
    #
    # Five surfaces, and the S01 finding is why they are five: the user message
    # was clean and the real value rode an ERROR payload nobody had a row for.
    # The capture is taken from the SAME call that does the delivery, so it
    # cannot describe a payload the model never saw.

    def _capture_payload(self, name: str, text: str, real_text: str) -> None:
        if self._capture:
            if self._auto_manifest and self._manifest is not None:
                self._manifest = _manifest_at_delivery(
                    self._case5, self._manifest, name, real_text)
            self._payloads.append(canaries.CapturedPayload(
                name=name, text=text, real_text=real_text))

    def note_final(self, raw_reply: str, restored: str) -> None:
        """The two ends of the answer leg, both taken from the harness.

        `text` is the model's OWN bytes — what the gateway hands the restorer;
        `real_text` is what the customer receives. A real value in the first is
        the leak (the model held it); its presence in the second and absence
        from the first is the restore working, and the count says so."""
        self._capture_payload("final_answer", raw_reply, restored or raw_reply)

    def captured_payloads(self) -> tuple[canaries.CapturedPayload, ...]:
        """Every payload the run delivered, plus the composed model-bound one.

        THE COMPOSED REQUEST IS A BOUNDARY OF ITS OWN. Per-message capture proves
        each message was masked; it cannot prove the transcript the provider is
        actually sent is masked. `_on_masked_request` records the result of the
        existing production mask call at every push, before later notes can
        change the transcript or vault state.
        """
        return tuple(self._payloads)

    def _on_masked_request(self, masked: list[dict[str, object]]) -> None:
        self._capture_payload("model_request", json.dumps(masked, ensure_ascii=False),
                              json.dumps(self._transcript, ensure_ascii=False))

    def evidence(self) -> canaries.ProvenanceEvidence:
        """Provenance from the OBSERVER RECORD, used ONLY to classify a leak.

        `span_missed` compares the item's DECLARED range (construction) with the
        spans the masking record holds — the record answers «what was replaced»,
        the case answers «what should have been». This NEVER decides whether a
        leak exists: `payload_canaries.scan` decides that from the manifest and
        the delivered bytes, and the evidence only labels the result."""
        return canaries.evidence_from_spans(
            self._case5.base.pii, self.masked_spans(), self.substitutes_seen())

    def canary_report(self) -> canaries.CanaryReport:
        """The report for THIS run's delivered bytes — the real harness caller.

        NO MANIFEST, NO MEASUREMENT: a gateway that was handed no construction-
        time manifest reports NOT_MEASURED rather than reading a clean run off a
        scan it cannot ground."""
        if self._manifest is None:
            return canaries.not_measured(
                "the gateway carried no construction-time canary manifest")
        return canaries.scan(self._manifest, self.captured_payloads(), self.evidence())

    def capture(self, repeat: int) -> canaries.RunCapture:
        """THIS triple's manifest and the exact bytes it delivered, packaged for
        the run directory.

        S02 CAPTURE. `captured_payloads()` is the gateway's own memory and dies
        with the process; before `drive_v5` writes it to disk, a battery's bytes
        existed only in the worker that produced them, and `check_run` could only
        reconstruct them from `mentions` — the reconstruction the reviewer
        refused. This method is the ONE place that pairs the manifest with the
        delivered bytes, and both come from the run itself: the manifest was
        handed in at case construction, the bytes were appended as they were
        handed to the model. `repeat` is the arm's index and travels with the row
        because ONE case is run K times and the K rows must not be merged into
        one."""
        if not self._capture or self._manifest is None:
            raise canaries.CaptureError(
                f"{self._case5.base.id}|{repeat}: payload capture was not enabled")
        return canaries.RunCapture(case_id=self._case5.base.id, repeat=int(repeat),
                                   arm="I", manifest=self._manifest,
                                   delivered=self.captured_payloads())

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
            # The model's own bytes in place of THIS message: `served` is what
            # the provider is handed, `text` is what the customer wrote.
            self._capture_payload("model_input", served, text)
        return served

    def note_tool_call(self, name: str, arguments: dict[str, object]) -> None:
        """PLUS the canary capture: the arguments AS THE AGENT WROTE THEM.

        This is the leak surface — a real value here means the model held it.
        The restore that follows is the product working (the TOOL is supposed to
        get real values), so `restore_arguments` fills in the pre-mask text and
        the count of hidden canaries comes from the difference."""
        super().note_tool_call(name, arguments)
        self._capture_payload("tool_args", json.dumps(arguments, ensure_ascii=False), "")

    def restore_arguments(self, arguments: dict[str, object]):
        restored, residual = super().restore_arguments(arguments)
        if self._capture and self._payloads and self._payloads[-1].name == "tool_args":
            self._payloads[-1] = replace(
                self._payloads[-1], real_text=json.dumps(restored, ensure_ascii=False))
            if self._auto_manifest and self._manifest is not None:
                self._manifest = _manifest_at_delivery(
                    self._case5, self._manifest, "tool_args",
                    self._payloads[-1].real_text)
        return restored, residual

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
        # The text the MODEL read back, on the shape it read it: an error payload
        # is its own boundary (S01), even though both cross the same leg.
        forced = log.parsed is None and log.refusal is None
        self._capture_payload("tool_error" if forced else "tool_result",
                              masked.masked, masked.text)
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
            forced=forced))
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
    """The customer's OWN strings — never counted as a substitute of ours.

    The settlement inside a minted address is real (vault `_settlement_of`), so
    without this the pre-gate would call every reply that names the customer's
    own town «неверно».

    THE WHOLE VALUE AS WELL AS THE PARTS, because `judge.own_vocabulary` reads
    WORDS off these strings and a part list carries none of the words a value
    has outside its parts: a spoken date's only part is `iso`, so «двадцать
    шестое ноября восемьдесят второго года» contributed nothing and the gate
    refused honest answers on «второго» and «седьмого» — the customer's own
    words, which a minted spoken date shares by arithmetic. The canonical is
    here for the other direction: it carries the nominative («таисия») that
    the inflected surface («таисию») does not.
    """
    return tuple(sorted({value for item in case.base.pii
                         for value in (*item.parts.values(), item.value, item.canonical)
                         if value}))


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


def turn_restorer(case: CaseV5, gateway: RealGateway) -> Callable[[str], str]:
    """ONE restoration leg for EVERY turn of one case.

    A `streaming` case is delivered chunk by chunk from the first turn, not
    from the last: the sidecar's per-field contract applies to every
    `delta.content` the agent produces. The harness used to restore the final
    reply through the chunk contract (F3.1) and every EARLIER turn whole — so
    the judge read, and `turn_residual` counted, intermediate turns nobody was
    served. Measured on 250 intermediate replies built from the corpus's own
    streaming cases through the production masking path: 4 differ between the
    two restorations and in ONE of them a minted substitute still stands in the
    chunked text while the whole-text leg resolved it — a residual the customer
    saw and the record denied.

    The final turn is then the chunked restoration BY CONSTRUCTION rather than
    by a second pass over it (`with_streamed_answer`, deleted): `answer_leg`
    and this leg apply the same function to the same string, so the record
    cannot hold two answers.
    """
    if not case.streaming:
        return gateway.restore_text
    vault = gateway.vault

    def chunked(text: str) -> str:
        return restore_stream(text, vault, STREAM_CHUNK)

    return chunked


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


class ArmConnector(Protocol):
    async def control(self, case: CaseV5, arm: str, repeat: int, backend: BackendV5,
                      model: str, cap: float, run_id: str) -> v4_harness.ArmOutcome: ...

    async def intervention(self, case: CaseV5, repeat: int, gateway: GatewayV5,
                           backend: BackendV5, model: str, cap: float,
                           run_id: str) -> ArmOutcomeV5: ...


class ClaudeArms:
    """Keep the existing Claude execution path available through the same interface."""

    def __init__(self, timeout_scale: float = 1.0) -> None:
        # `--timeout-scale`, carried here because the per-case timeout is a
        # property of how ONE arm executes, not of the retry driver. The same
        # value rides in `DrivePolicy.timeout_scale` (the run-level record) and
        # in `meta.provider`; both arms and the policy are built from the one
        # CLI flag in `main`, so they cannot drift.
        self.timeout_scale = timeout_scale

    async def control(self, case: CaseV5, arm: str, repeat: int, backend: BackendV5,
                      model: str, cap: float, run_id: str) -> v4_harness.ArmOutcome:
        return await _guarded_control(case, arm, repeat, backend, model, cap, run_id,
                                      self.timeout_scale)

    async def intervention(self, case: CaseV5, repeat: int, gateway: GatewayV5,
                           backend: BackendV5, model: str, cap: float,
                           run_id: str) -> ArmOutcomeV5:
        return await _guarded_arm_v5(case, repeat, gateway, backend, model, cap, run_id,
                                     self.timeout_scale)


class GatewayHooks:
    """Connect model events to the existing gateway and benchmark tool backend."""

    def __init__(self, case: CaseV5, gateway: GatewayV5 | PassThrough,
                 backend: BackendV5) -> None:
        self.case = case
        self.gateway = gateway
        self.backend = backend
        self.calls: list[ObservedCall] = []
        self.turns: list[int] = []
        self.turn = -1
        # THE PROVIDER CHRONOLOGY (Codex contract, 2026-09-27). `responses` is
        # one entry per completed provider response the connector reported
        # through `response`; `call_requests` maps each accepted call to the
        # `request` of the response that emitted it. `_pending_request` is the
        # response whose function calls are being processed RIGHT NOW, and
        # `_unmapped` records a call that arrived with no reported response —
        # such an arm yields `None`, never a manufactured request.
        self.responses: list[ModelResponse] = []
        self.call_requests: list[int] = []
        self._pending_request: int | None = None
        self._unmapped_call = False

    def user(self, index: int) -> str:
        self.turn = index
        # A call that arrives before THIS turn's first reported response has no
        # response to belong to. Clearing here makes such a call an UNMAPPED one
        # instead of letting it silently inherit the previous turn's ordinal.
        self._pending_request = None
        return self.gateway.push_user(index)

    def assistant(self, text: str) -> None:
        if text:
            self.gateway.note(text)

    def response(self, text: str) -> None:
        """One COMPLETED provider response, BEFORE its function calls run.

        Called even when `text` is empty: a pure tool-call turn returned no
        prose and that is an observation, not an absence. `available_results`
        is the number of accepted results already in hand — the count the two
        calls of ONE response both see, and which the NEXT response sees raised
        by them. `restored` goes through the gateway's CURRENT state, the same
        object `answer_leg` will use for the final reply.
        """
        request = len(self.responses) + 1
        self.responses.append(ModelResponse(
            request=request, turn=self.turn, available_results=len(self.calls),
            raw=text, restored=self.gateway.restore_text(text)))
        self._pending_request = request

    def model_trace(self) -> ModelTrace | None:
        """The chronology, or None only when the connector never reported one.

        NO RESPONSE AT ALL is the legacy connector (Claude, a double): there is
        no chronology to report and `None` is the honest answer, even if it made
        calls. But ANY response means this connector speaks the hook, so a call
        it could not place, or a count that does not line up, is BROKEN
        chronology rather than silence — `None` there would erase the evidence.
        """
        if not self.responses:
            return None
        if self._unmapped_call:
            raise HarnessError(
                "model_trace: a tool call arrived with no reported provider response")
        if len(self.call_requests) != len(self.calls):
            raise HarnessError(f"model_trace: {len(self.call_requests)} mapped calls for "
                               f"{len(self.calls)} recorded calls")
        return ModelTrace(responses=tuple(self.responses),
                          call_requests=tuple(self.call_requests))

    def tool(self, name: str, arguments: dict[str, Json]) -> ToolResult:
        written: dict[str, object] = dict(arguments)
        self.gateway.note_tool_call(name, written)
        restored, residual = self.gateway.restore_arguments(written)
        log = self.backend.call(name, restored)
        ordinal = sum(call.name == name and turn == self.turn
                      for call, turn in zip(self.calls, self.turns, strict=True))
        self.calls.append(ObservedCall(
            name=name, written=written, restored=restored, residual=residual,
            refusal_path=log.refusal.path if log.refusal else '',
            refusal_rule=log.refusal.rule if log.refusal else '', parsed=log.parsed,
            seq=len(self.calls) + 1))
        self.turns.append(self.turn)
        # EACH ACCEPTED CALL MAPS TO THE RESPONSE THAT EMITTED IT. Two calls of
        # one response share its `request`; the second one did NOT see the
        # first's result (`available_results` was fixed before either ran).
        if self._pending_request is None:
            self._unmapped_call = True
        else:
            self.call_requests.append(self._pending_request)
        if isinstance(self.gateway, GatewayV5):
            served = self.gateway.push_call(name, log, self.backend.form_of(log.seq),
                                           self.turn, ordinal)
        else:
            served = self.gateway.push_tool(name, log.result_text)
        return ToolResult(served, log.refusal is None)


def connector_tools(schemas: list[dict[str, object]]) -> tuple[ToolSpec, ...]:
    tools: list[ToolSpec] = []
    for schema in schemas:
        function = json_object(schema['function'])
        tools.append(ToolSpec(str(function['name']), str(function['description']),
                              json_object(function['parameters'])))
    return tuple(tools)


class ConnectedArms:
    """Run all three arms through one injected model connector."""

    def __init__(self, connector: AgentConnector, max_calls: int = DEFAULT_MAX_CALLS,
                 timeout_scale: float = 1.0) -> None:
        self.connector = connector
        self.max_calls = max_calls
        # `--timeout-scale`: same comment as `ClaudeArms` — the per-case timeout
        # is an arm-execution property, so the connector carries the scale it
        # hands to `converse(... timeout_s=...)`.
        self.timeout_scale = timeout_scale

    async def _run(self, case: CaseV5, arm: str, repeat: int,
                   gateway: GatewayV5 | PassThrough, backend: BackendV5,
                   model: str, cap: float) -> tuple[v4_harness.ArmOutcome, ArmRunV5 | None]:
        hooks = GatewayHooks(case, gateway, backend)
        system = gateway.push_system(case.base.messages[0].content)
        tools = connector_tools(gateway.tools())
        indices = tuple(i for i, message in enumerate(case.base.messages)
                        if message.role == 'user')
        result = await self.connector.converse(system, tools, indices, hooks,
                                               scaled_timeout(case.base, self.timeout_scale),
                                               self.max_calls)
        if gateway.faults:
            raise HarnessError(f'{case.base.id}/{arm}: {gateway.faults[0]}')
        raw = next((reply for reply in reversed(result.replies) if reply.strip()), '')
        leg = (answer_leg(raw, case.streaming, gateway.vault, gateway.restore_text)
               if isinstance(gateway, GatewayV5) else None)
        reply = leg.reply if leg else gateway.restore_text(raw)
        # THE CANARY BOUNDARY THE HARNESS ALONE CAN NAME: the model's own bytes
        # and the customer's restored answer, both taken here — in the real
        # caller — so the capture cannot be driven by a test-only path.
        if isinstance(gateway, GatewayV5):
            gateway.note_final(raw, reply)
        base = ArmRun(case_id=case.base.id, arm=arm, repeat=repeat, calls=tuple(hooks.calls),
                      state=backend.snapshot(), reply=reply, termination='done',
                      cost_usd=result.usage.cost_usd,
                      substitutes=substitutes_for(case.base, gateway.substitutes_seen())
                      if isinstance(gateway, GatewayV5) else {},
                      masked_spans=gateway.masked_spans() if isinstance(gateway, GatewayV5) else {})
        meta = ArmMeta(model=model, turns=result.turns, duration_ms=result.duration_ms,
                       session_id=result.session_id, subtype='success', is_error=False,
                       api_error_status=None, errors=(), reason='', cap_usd=cap)
        outcome = v4_harness.ArmOutcome(base, meta)
        if not isinstance(gateway, GatewayV5) or leg is None:
            return outcome, None
        run = ArmRunV5(base=base, reply_raw=raw, control_reply='',
                      tool_results=gateway.tool_records(), mentions=gateway.mentions(),
                      turn_replies=restored_turn_replies(result.replies, turn_restorer(case, gateway)),
                      call_turns=tuple(hooks.turns), request_count=gateway.request_index,
                      stream_mismatch=leg.mismatch, reply_whole=leg.reply_whole, turn_residual=0,
                      # The provider chronology, if this connector reported it.
                      # None (not a guess) for a connector that never called
                      # `response`.
                      model_trace=hooks.model_trace())
        return outcome, run

    async def control(self, case: CaseV5, arm: str, repeat: int, backend: BackendV5,
                      model: str, cap: float, run_id: str) -> v4_harness.ArmOutcome:
        try:
            outcome, _ = await self._run(case, arm, repeat, PassThrough(case.base),
                                          backend, model, cap)
            return outcome
        except asyncio.TimeoutError as error:
            # OUR OWN `wait_for` deadline on the connector — a verdict, not a
            # blip. ConnectorError (DeepSeek cut the reply) is NOT caught here:
            # it is a RuntimeError, so it falls to the guard below and
            # `arm_verdict` re-raises it as a transient blip for §1.4's retry.
            return v4_harness._failed_arm(case.base, arm, repeat, 'timeout',
                                         type(error).__name__ + ': ' + str(error), cap, cap, run_id)
        except (HarnessError, OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
            return arm_verdict(case.base, arm, repeat, error, cap, run_id, self.timeout_scale)

    async def intervention(self, case: CaseV5, repeat: int, gateway: GatewayV5,
                           backend: BackendV5, model: str, cap: float,
                           run_id: str) -> ArmOutcomeV5:
        try:
            outcome, run = await self._run(case, 'I', repeat, gateway, backend, model, cap)
            if run is None:
                raise HarnessError('intervention did not record observations')
            return ArmOutcomeV5(outcome, run)
        except asyncio.TimeoutError as error:
            # Same line as `control`: our deadline is a verdict, ConnectorError
            # is a transient blip re-raised by `arm_verdict` below.
            outcome = v4_harness._failed_arm(case.base, 'I', repeat, 'timeout',
                                           type(error).__name__ + ': ' + str(error), cap, cap, run_id)
            return ArmOutcomeV5(outcome, _empty_run(case, repeat))
        except (HarnessError, OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
            return ArmOutcomeV5(arm_verdict(case.base, 'I', repeat, error, cap, run_id, self.timeout_scale),
                                _empty_run(case, repeat))


async def run_arm_v5(case: CaseV5, arm: str, repeat: int, gateway: GatewayV5,
                     backend: BackendV5, model: str, cap: float, run_id: str,
                     timeout_scale: float = 1.0) -> ArmOutcomeV5:
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

    await asyncio.wait_for(drive(), timeout=scaled_timeout(case.base, timeout_scale))
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
    turn_replies = restored_turn_replies(replies, turn_restorer(case, gateway))
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
                   turn_residual=0,
                   # THE CLAUDE LEG HAS NO PROVIDER CHRONOLOGY. It runs through
                   # the Agent SDK, which reports no per-response boundary, so
                   # the field is an explicit None rather than a manufactured
                   # request per call.
                   model_trace=None)
    return ArmOutcomeV5(v4_harness.ArmOutcome(base, meta), run)


def transient_blip(error: BaseException) -> bool:
    """Флаки-отказ провайдера НА ПЛЕЧЕ — и никогда наш собственный дедлайн (§1.4).

    `runinfo.is_transient_error` держит транспорт (`is_transport_error` — закрытая
    таблица имён классов SDK плюс `ConnectionError`/`TimeoutError`) И три
    флаки-класса (`ConnectorError`/`ConnectorLimit`/`WriterError`). На плече
    встроенный `TimeoutError` надо вычесть: `run_arm_v5` и v4's `run_arm`
    ограничивают плечо собственным `asyncio.wait_for`, а
    `asyncio.TimeoutError is TimeoutError` начиная с 3.11 — то есть дедлайн,
    который мы поставили сами, неотличим по типу от таймаута провайдера.
    Повторять его значит заново прождать `_timeout(case)` секунд и заплатить
    потолок за одно зависшее плечо, а у него уже есть честный ответ — v4's
    `timeout` с полным начислением. Собственный таймаут SDK приходит СВОИМ
    классом (`APITimeoutError`), он в таблице имён и повторяется.
    """
    if isinstance(error, asyncio.TimeoutError):
        return False
    return runinfo.is_transient_error(error)


def arm_verdict(case: Case, arm: str, repeat: int, broken: BaseException, cap: float,
                run_id: str, timeout_scale: float = 1.0) -> v4_harness.ArmOutcome:
    """Вердикт v4 по исключению ОДНОГО плеча — одно место на все три.

    ОБРЫВ ПРОВАЙДЕРА ОТСЮДА УЛЕТАЕТ НАВЕРХ, и это вся починка §1.4: защита
    была написана вокруг тройки (`run_with_retries`), а до неё не доезжало
    ничего — `ConnectionError` это `OSError`, `asyncio.TimeoutError` ловился
    первым, и оба превращались в снятое плечо ещё внутри стража. Провайдер
    моргал — прогон молча терял плечо и шёл дальше с числом, которое уже
    ничего не значит.

    ВЕРДИКТЫ — v4's, слово в слово (`bench/agentpii4/harness.py::_guarded_arm`),
    потому что записи плеч читает v4's же `arm_record`, а второе написание
    термина «timeout» — это второй словарь, который придётся держать равным
    первому. Своя функция, а не вызов `v4_harness._guarded_arm`, по одной
    причине: v4 — база сравнения, его файл не наш, а его страж глотает обрыв.
    Всё, что не наше и не обрыв, летит дальше: `except Exception` у
    вызывающего не ловит `BaseException`, так что `CancelledError` и
    `KeyboardInterrupt` проходят насквозь, как и раньше.
    """
    if transient_blip(broken):
        raise broken
    if isinstance(broken, asyncio.TimeoutError):
        return v4_harness._failed_arm(case, arm, repeat, "timeout",
                                      f"таймаут {scaled_timeout(case, timeout_scale):.0f}s",
                                      cap, cap, run_id)
    if isinstance(broken, HarnessError):
        return v4_harness._failed_arm(case, arm, repeat, "harness_error",
                                      f"HarnessError: {broken}", cap, 0.0, run_id)
    if isinstance(broken, (OSError, ValueError, KeyError, TypeError, RuntimeError)):
        # An exception out of the masking path is the PRODUCT failing closed —
        # `gateway_5xx` on the gateway arm, counted, never excluded.
        kind = "gateway_5xx" if arm == "I" else "harness_error"
        return v4_harness._failed_arm(case, arm, repeat, kind,
                                      f"{type(broken).__name__}: {broken}", cap, 0.0, run_id)
    raise broken


async def _guarded_arm_v5(case: CaseV5, repeat: int, gateway: GatewayV5, backend: BackendV5,
                          model: str, cap: float, run_id: str,
                          timeout_scale: float = 1.0) -> ArmOutcomeV5:
    """Never raises for one arm — EXCEPT on a provider blip, which §1.4's retry
    owns and which `arm_verdict` sends back up.

    v4's rule otherwise, and v4's charge for a timeout (it DID bill, and a
    ledger that books it at zero lets the next case spend money already gone).
    """
    try:
        return await run_arm_v5(case, "I", repeat, gateway, backend, model, cap, run_id,
                                timeout_scale)
    except Exception as broken:      # noqa: BLE001 — `arm_verdict` re-raises what is not ours
        failed = arm_verdict(case.base, "I", repeat, broken, cap, run_id, timeout_scale)
    return ArmOutcomeV5(failed, _empty_run(case, repeat))


async def _guarded_control(case: CaseV5, arm: str, repeat: int, backend: BackendV5,
                           model: str, cap: float, run_id: str,
                           timeout_scale: float = 1.0) -> v4_harness.ArmOutcome:
    """Плечо контроля — v4's `run_arm` под НАШИМ стражем.

    v4's `_guarded_arm` делает то же самое, но обрыв провайдера у него никуда
    не улетает, а `bench/agentpii4/` — база сравнения и правится не здесь. Так
    что зовём v4's `run_arm` (его опции, его таймаут, его запись) и отдаём
    исключение общему `arm_verdict`: контрольные плечи ходят в ту же модель и
    моргает провайдер на них ровно так же, как на плече шлюза.

    `timeout_scale` сюда НЕ доезжает до v4's `run_arm` (тот сам зовёт v4's
    `_timeout` — базлайн не двигается); он нужен только `arm_verdict`, чтобы
    сообщение «таймаут …s» в записи назвало тот же дедлайн, что и плечо I.
    """
    try:
        return await v4_harness.run_arm(case.base, arm, repeat, PassThrough(case.base),
                                        backend, model, cap, run_id)
    except Exception as broken:      # noqa: BLE001 — `arm_verdict` re-raises what is not ours
        return arm_verdict(case.base, arm, repeat, broken, cap, run_id, timeout_scale)


def _empty_run(case: CaseV5, repeat: int) -> ArmRunV5:
    base = ArmRun(case_id=case.base.id, arm="I", repeat=repeat, calls=(), state=(), reply="",
                  termination="harness_error", cost_usd=0.0, substitutes={}, masked_spans={})
    return ArmRunV5(base=base, reply_raw="", control_reply="", tool_results=(), mentions=(),
                    turn_replies=(), call_turns=(), request_count=0, stream_mismatch=False,
                    reply_whole="", turn_residual=0, model_trace=None)


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
    if refused is not None:
        verdict = refused
    elif config is None:
        verdict = JudgeVerdict(label="", reason="судья выключен (--no-judge)",
                               judged_by="none", cost_usd=0.0)
    else:
        try:
            verdict = await judge_prompt(config, request, prompt)
        except v3_judge.BudgetExhausted as exhausted:
            # A CEILING REACHED IS NOT A REASON TO LOSE THREE PAID ARMS. The
            # judge reserves from the SAME ledger as the arms, INSIDE
            # `judge._ask`, long after C, I and C′ have finished and been
            # charged; the refusal used to travel out of `judge_prompt`,
            # `judge_triple` and `run_triple_v5` — whose only handlers are the
            # OUTER reservation and `LeakedPrompt` — and out of `drive_v5`,
            # which has none, killing the whole run. Caught HERE rather than
            # around `judge_triple`, because `turn_residual` and the prompt's
            # hash are already measured at this point and an outer catch would
            # replace both with a zero nobody can tell from silence.
            # THE PRICE, STATED: a verdict abandoned between its two asks
            # loses the FIRST ask's cost from `judge_cost_usd`. The ledger
            # itself is right (`judge._ask` settles in a `finally`), so the
            # ceiling still holds inside the run; only a later `--resume`
            # under-charges itself by at most `QUERY_CAP_USD`. Preserving it
            # would mean catching inside `judge_prompt`, and that module may
            # not import `BudgetExhausted` at all — v3's judge drags `pseudex`
            # in through `score` (judge.py's `Ledger` Protocol says why).
            print(f"[judge] {case.base.id}|{run.base.repeat}: {JUDGE_SKIPPED_BUDGET}: "
                  f"{exhausted}", file=sys.stderr, flush=True)
            verdict = JudgeVerdict(label="", reason=f"{JUDGE_SKIPPED_BUDGET}: {exhausted}",
                                   judged_by="none", cost_usd=0.0)
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

    WHICH restoration is the caller's to choose (`turn_restorer`): a streaming
    case is read chunk by chunk from its first turn, and this function must not
    know two ways to restore a string. The LAST non-empty entry is the same
    text `raw_reply` is taken from, so under one leg it restores to the same
    final answer `answer_leg` scored — the record holds one answer because one
    function produced both, not because a second pass copied it over. The
    dialogue the judge sees drops the last non-empty turn either way: the
    answer is evidence and has its own section.
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
                        model: str, run_id: str, arms: ArmConnector) -> TripleResult:
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
        "status": "refused", "reason": "", "attempts": 1, "arms": {}, "judge": {}}
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
    # S02 CAPTURE. The gateway constructs canaries from case-declared literals
    # and records placement from each raw payload at delivery. The real runner
    # persists both manifest and delivered bytes after intervention.
    captures: tuple[canaries.RunCapture, ...] = ()
    try:
        control = await arms.control(case, "C", repeat, seed_backend_v5(case),
                                         model, cap, run_id)
        outcomes.append(control)
        spent += control.run.cost_usd
        if control.run.termination in EXCLUDED_TERMINATIONS:
            triple["status"] = "excluded"
            triple["reason"] = f"C: {control.run.termination} {control.meta.reason}".strip()
            return TripleResult(outcomes, None, (), None, triple)
        gateway = GatewayV5(case, detector, Vault(":memory:", _ORG), AuditLog(":memory:"),
                            MaskCache(256), capture=True)
        intervention, second = await asyncio.gather(
            arms.intervention(case, repeat, gateway, seed_backend_v5(case), model, cap, run_id),
            arms.control(case, "C2", repeat, seed_backend_v5(case), model, cap, run_id))
        outcomes.extend((intervention.base, second))
        spent += intervention.base.run.cost_usd + second.run.cost_usd
        # THE CAPTURE IS TAKEN FROM THE ARM THAT ACTUALLY RAN THE GATEWAY, after
        # it returned, and it is taken whether the judge spoke or not: a triple
        # the judge refused still delivered bytes, and «the judge was skipped» is
        # not «the model was sent nothing».
        captures = (gateway.capture(repeat),)
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
            triple["judge"] = judge_summary(judged.verdict)
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
    return TripleResult(outcomes, gateway_run, hops, judged, triple, captures)


def judge_summary(verdict: JudgeVerdict) -> dict[str, object]:
    """What the TRIPLE row says about the judge.

    THE REASON RIDES HERE TOO, not only in `<run>.judge.jsonl`. A verdict with
    an empty label reads the same in the triples file whether the judge was
    switched off, refused to quote, or was never asked because the run's
    ceiling was reached (`JUDGE_SKIPPED_BUDGET`) — and the triples file is what
    an operator opens when a run cost less than it should have.

    A named function rather than a literal inside `run_triple_v5`, for the
    reason `with_control_reply` and `charged` are ones: that function needs a
    live model, and a claim only a paid run can check is a claim nobody checks.
    """
    return {"label": verdict.label, "judged_by": verdict.judged_by,
            "cost_usd": verdict.cost_usd, "reason": verdict.reason}


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
                  model: str, run_id: str, arms: ArmConnector) -> TripleRunner:
    """`run_triple_v5` with the run's constants bound — the `TripleRunner`
    `drive_v5` takes."""
    async def run(case: CaseV5, repeat: int) -> TripleResult:
        return await run_triple_v5(case, repeat, detector, ledger, config, model, run_id, arms)
    return run


# --- driving, and writing every file the report reads ---------------------------------------

class TransportExhausted(HarnessError):
    """`policy.attempts` попыток подряд оборвались на транспорте.

    Отдельный класс, а не `HarnessError` с текстом: драйвер обязан отличить
    «провайдер оборвался N раз» (случай снимается, прогон идёт дальше — §1.4)
    от «наш дефект» (исключение летит наружу и прогон падает), и различать их
    по подстроке в сообщении — это тот самый разбор текста, который перестаёт
    работать при первой же правке формулировки.
    """


@dataclass(frozen=True)
class DrivePolicy:
    """Что драйвер делает с обрывом провайдера (§1.4) и с уехавшей ценой (§7.1).

    `pause` и `jitter` — ПАРАМЕТРЫ, а не `asyncio.sleep` и `random.random`
    внутри: проверка отступа, которая честно спит 2, 4 и 8 секунд, добавляет
    четырнадцать секунд к каждому прогону батареи, и её через неделю выключат.
    `expected_per_case_usd` — точка оценки §1.1, делённая на тройки; ноль
    означает «оценки не было», и тогда стоп-кран не вооружён (см.
    `runinfo.brake_verdict`), а не срабатывает наугад.

    `timeout_scale` — множитель per-case таймаута (`--timeout-scale`). Это
    свойство ИСПОЛНЕНИЯ плеча, а не повтора, поэтому до мест исполнения его
    несёт коннектор (`ClaudeArms`/`ConnectedArms`); здесь поле живёт как
    запись настройки прогона рядом с остальными ручками драйвера, и в
    `main` оно берётся из того же флага, что и коннектор.
    """

    attempts: int
    base_s: float
    pause: Callable[[float], Awaitable[None]]
    jitter: Callable[[], float]
    expected_per_case_usd: float
    timeout_scale: float = 1.0


@dataclass(frozen=True)
class DriveResult:
    """Что драйвер знает по окончании и чего нет в файлах прогона.

    `transport_terminated` и `stopped` попадают в строку реестра и в
    последние строки на экране: прогон, остановленный стоп-краном, и прогон,
    доехавший до конца, различаются только здесь — числа в `<run>.triples.jsonl`
    у них одинаково честные и одинаково неполные.
    """

    triples: list[dict[str, object]]
    transport_terminated: int
    stopped: str


def transport_triple(case: CaseV5, repeat: int, attempts: int, error: str) -> dict[str, object]:
    """Строка тройки для случая, снятого обрывом провайдера (§1.4).

    ФОРМА СТРОКИ — ТА ЖЕ, что у `run_triple_v5`, и статус взят из уже
    существующего словаря (`excluded`): тогда отчёт исключает случай из
    знаменателей тем же кодом, которым исключает плечо, не доигравшее до конца,
    а новое слово в статусе пришлось бы учить каждому читателю тройки.
    Причина называет `runinfo.TRANSPORT_TERMINATED`, так что «сколько снял
    провайдер» считается по одной подстроке, а не по догадке.

    `cost_usd` — ноль: деньги, которые успели списаться до обрыва, уже в
    `<run>.spend.tsv` (леджер оседает в `finally`), и отчёт печатает журнал
    рядом с суммой троек — расхождение видно, а выдуманное число в строке
    тройки не видно никак.
    """
    return {"case_id": case.base.id, "repeat": repeat, "kind": case.base.kind,
            "behaviour": case.behaviour, "register": case.base.register,
            "cluster": case.base.cluster, "cap_usd": round(v4_harness.cap_usd(case.base) * 3, 6),
            "cost_usd": 0.0, **r.triple_totals_to_json(triple_totals(None, 0)),
            "status": "excluded",
            "reason": f"{runinfo.TRANSPORT_TERMINATED}: {error} (попыток {attempts})",
            "attempts": attempts, "arms": {}, "judge": {}}


async def run_with_retries(run_one: TripleRunner, case: CaseV5, repeat: int,
                           policy: DrivePolicy) -> TripleResult:
    """Одна тройка с повтором на флаки-отказе — экспоненциальный отступ с
    джиттером (`policy.base_s` как первый отступ), `policy.attempts` попыток,
    потом `TransportExhausted`.

    `except Exception` здесь НЕ глотает ничего: всё, что не признано флаки
    (`runinfo.is_transient_error` — транспорт + ConnectorError/ConnectorLimit +
    WriterError), поднимается дальше немедленно. Повторять наш собственный
    дефект с отступом значит несколько раз подождать перед тем же отказом и
    спрятать причину за словом «флаки».

    ПОВТОР НЕ ПЛОДИТ СТРОКИ. Возвращается ПЕРВЫЙ успешный `TripleResult` (его
    `triple` и пишется в `<run>.triples.jsonl`), а сколько попыток на него ушло
    штампуется в `triple["attempts"]`. Прерванные попытки не пишут ничего — это
    та же тройка, а не новый repeat (`--repeats` — другое, K ПРОГОНОВ всех
    троек).
    """
    last = ""
    for attempt in range(1, policy.attempts + 1):
        try:
            result = await run_one(case, repeat)
            result.triple["attempts"] = attempt
            return result
        except Exception as error:
            if not runinfo.is_transient_error(error):
                raise
            last = f"{type(error).__name__}: {error}"
            print(f"  ОБРЫВ {case.base.id}|{repeat} попытка {attempt}/{policy.attempts}: {last}",
                  file=sys.stderr, flush=True)
            if attempt < policy.attempts:
                await policy.pause(runinfo.backoff_seconds(attempt, policy.jitter(), policy.base_s))
    raise TransportExhausted(last)


async def drive_v5(cases: Sequence[CaseV5], repeats: int, run_one: TripleRunner,
                   run_dir: Path, run_id: str, concurrency: int,
                   already: frozenset[tuple[str, int]], policy: DrivePolicy) -> DriveResult:
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
    # S02 CAPTURE. NOT a `RUN_FILES` entry, and that is deliberate: the artifact
    # holds the corpus's own delivered bytes, and `RUN_FILES` is the list a
    # consumer iterates to build the run's outward documents. `records.run_file`
    # refuses a name the contract does not know, which is the guard that keeps
    # this file out of `<run>.meta.json`, `<run>.report.json` and
    # `<run>.public.json` — a run's public JSON must never carry a corpus value.
    triples: list[dict[str, object]] = []
    total = len(jobs)
    done = 0
    spent = 0.0
    transport = 0
    stopped = ""

    # An empty hops file is a valid measurement when every selected case is
    # excluded before the intervention arm.  A missing file means corruption
    # and report.py deliberately refuses it, so establish the distinction
    # before the first network call rather than only on the first hop.
    hops_sink.touch(exist_ok=True)

    async def worker(case: CaseV5, repeat: int) -> None:
        nonlocal done, spent, transport, stopped
        async with limiter:
            # СТОП-КРАН ПРОВЕРЯЕТСЯ ПЕРЕД ЗАХВАТОМ, а не после: `asyncio.gather`
            # поставил в очередь все задания сразу, и единственный момент, когда
            # заданию можно не начинаться, — до первого вызова модели.
            if stopped:
                return
            try:
                result = await run_with_retries(run_one, case, repeat, policy)
            except TransportExhausted as gone:
                # §1.4: случай снят, ПРОГОН ИДЁТ ДАЛЬШЕ. Строка тройки пишется
                # обязательно — случай, о котором не написано ничего, читается
                # как случай, который не выбирали.
                transport += 1
                row = transport_triple(case, repeat, policy.attempts, str(gone))
                r.append_row(triples_sink, row)
                triples.append(row)
                done += 1
                print(f"  [{done}/{total}] {case.base.id}|{repeat} "
                      f"{runinfo.TRANSPORT_TERMINATED} — {gone}", flush=True)
                return
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
            # BEFORE the triple row, for the reason every other per-triple sink is:
            # the bytes are on disk before the next triple starts, so an outage
            # costs one capture and not the run. A triple with no capture (a
            # budget refusal, an excluded C) writes no row at all — an empty row
            # would claim the boundaries were reached and delivered nothing.
            for captured in result.captures:
                canaries.append_capture(run_dir, run_id, captured)
            r.append_row(triples_sink, result.triple)
            triples.append(result.triple)
            done += 1
            spent += float(result.triple["cost_usd"])
            judge = dict(result.triple.get("judge") or {})       # type: ignore[arg-type]
            print(f"  [{done}/{total}] {case.base.id}|{repeat} {result.triple['status']} "
                  f"${float(result.triple['cost_usd']):.4f} хопов {len(result.hops)} "
                  f"судья={judge.get('label') or '—'}", flush=True)
            # §7.1: средняя цена случая против ожидаемой. Считается ПОСЛЕ записи
            # строк этой тройки — тройка, за которую уже заплачено, обязана
            # остаться на диске, чем бы ни кончился прогон.
            refused = runinfo.brake_verdict(done, spent, policy.expected_per_case_usd,
                                            f"{case.base.id}|{repeat}")
            if refused and not stopped:
                stopped = refused
                print(f"\n{refused}", file=sys.stderr, flush=True)

    await asyncio.gather(*(worker(case, repeat) for case, repeat in jobs))
    return DriveResult(triples=triples, transport_terminated=transport, stopped=stopped)


def write_corpus(run_dir: Path, cases: Sequence[CaseV5], digest: str) -> None:
    """The two snapshots, written before the first dollar: `--report` replays
    against what was actually played, never against the tree as it is now."""
    (run_dir / "corpus.json").write_text(json.dumps(
        {"corpus": [case.base.to_json() for case in cases], "digest": digest},
        ensure_ascii=False), encoding="utf-8")
    (run_dir / "corpus.v5.json").write_text(json.dumps(
        {"corpus": [case_v5_to_json(case) for case in cases], "digest": digest},
        ensure_ascii=False), encoding="utf-8")


def write_meta(run_dir: Path, run_id: str, model: str, judge_model: str, tier: str,
               repeats: int, digest: str, ceiling_usd: float, spent_usd: float,
               label: str, note: str, started: str, wall_s: float,
               extra: dict[str, object]) -> Path:
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

    `extra` IS a parameter, and the difference is who owns the fact. The
    provenance of the tree (§6.1), the provider with its prices (§4.1) and what
    the gateway arm ran against (§4.2) are produced by `build` and `provider`
    before the run starts; this function may not recompute them without becoming
    a second opinion about the commit a run is tied to. It merges rather than
    nests so `report.meta_of` keeps reading one flat object, and a key that
    collides with one of the named fields is a refusal — silently overwriting
    `run_id` from a caller's dict is exactly the shape that makes a run file
    describe another run.

    МЕТКА И ЗАМЕТКА (§1.3) ЖИВУТ ЗДЕСЬ ЖЕ, а не только в реестре: `runs.json`
    можно потерять вместе с репозиторием, а каталог прогона уезжает к тому, кто
    его разбирает, и «прогон от 23.09» без метки не значит ничего уже через
    месяц. `started` и `wall_s` — потому что оценка времени следующего прогона
    (§1.1) строится по факту предыдущего, а `finished` в одиночку длительности
    не даёт.
    """
    path = r.run_file(run_dir, run_id, "<run>.meta.json")
    written: dict[str, object] = {
        "run_id": run_id, "benchmark": BENCHMARK, "model": model,
        "judge_model": judge_model, "tier": tier, "repeats": repeats, "digest": digest,
        "ceiling_usd": ceiling_usd, "spent_usd": round(spent_usd, 6),
        "label": label, "note": note, "started": started, "wall_s": round(wall_s, 1),
        "prompt_sha256": prompt_sha256(),
        "finished": datetime.now(timezone.utc).isoformat()}
    collisions = sorted(set(extra) & set(written))
    if collisions:
        raise HarnessError(f"write_meta: {collisions} уже описаны самим прогоном — "
                           f"блок, переписывающий их, сделал бы файл описанием другого прогона")
    written.update(extra)
    path.write_text(json.dumps(written, ensure_ascii=False, indent=2), encoding="utf-8")
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


def capture_run_repairs(run_dir: Path) -> Path | None:
    """M04: freeze THIS run's LOC repair witnesses while the engine is live.

    THE PRODUCER ASKS, THE SCORER READS. `report.frozen_score_and_observations`
    must print a saved number that cannot move when `register_spelling` is
    edited, so the engine is consulted exactly once — here, by the process that
    owns it at run time — and the answer is persisted as a versioned
    `repairs.json` beside the run's artifacts. Without this call every real run's
    LOC pairs stay UNMEASURED, which the report prints honestly and which is why
    a missing capture is a gap rather than a wrong number.

    THE OBSERVATIONS COME FROM THE SCORER'S OWN ENGINE-FREE READER
    (`report.v5_observations`, the same one `report.frozen_score_and_observations`
    uses), so the pair list is the artifact's own and not a second derivation of
    it: the table answers for exactly the pairs the report will score.

    FROZEN ONCE. A table already on disk is never rewritten — a `--report`
    replay of a finished directory must read the witnesses, not re-ask the
    engine, or the defect M04 removes comes back through the report path. And
    with no bundle leased nothing is frozen at all: an invented witness would be
    worse than the honest «не измерено»."""
    from bench.agentpii5 import frozen_oracle
    from pseudex.address import register_spelling
    from pseudex.assets import ASSETS

    path = frozen_oracle.repairs_path(run_dir)
    if path.exists() or not ASSETS.is_loaded:
        return None
    half = v5_report.v5_observations(run_dir, ())
    return frozen_oracle.capture_run_repairs(
        run_dir, frozen_oracle.repair_pairs(half.observations), register_spelling)


def finish_run(run_dir: Path, baseline: Path) -> list[str]:
    """The side-by-side and the two machine-readable halves beside it:
    `<run>.report.txt`, `<run>.gate.json`, `<run>.report.json`, `<run>.public.json`.

    `baseline` defaults to the run itself at the call site: the v4 block of a v5
    run IS a v4 report of v4-shaped files, so a run with no baseline still
    prints one — beside itself, which is honest and visibly useless.

    ONE FUNCTION WRITES ALL FOUR, and that is why the JSON is here rather than
    at the end of `main`: `--report` rebuilds a finished directory through this
    same call, and a JSON produced only by a live run would go stale the first
    time anybody replayed a report. The two assemblies (`report` builds one,
    `reportjson` another) read the same files with the same registry and cannot
    disagree; threading one `SideBySide` through both would move the decision of
    where `<run>.report.txt` lives out of `report.py` and into this module,
    which is the drift the file names exist to prevent.
    """
    # THE WITNESSES ARE FROZEN BEFORE ANY LINE IS PRINTED. `render_side_by_side`
    # scores through `report.frozen_score_and_observations`, which reads
    # `repairs.json`; capturing after it would print a run in which every LOC
    # pair was unmeasured and then freeze them, so the replay and the live
    # report would disagree about the same bytes on disk.
    capture_run_repairs(run_dir)
    lines = v5_report.render_side_by_side(run_dir, baseline)
    written = reportjson.write_side_by_side(run_dir, baseline)
    return lines + ["", f"машинный отчёт: {written.report.name} (ТЗ §5.1)",
                    f"публичная подстрока: {written.public.name} (ТЗ §5.3)"]


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


def foreign_run_ids(run_dir: Path, run_id: str) -> tuple[str, ...]:
    """Run ids already written into `run_dir` that are not `run_id`.

    EVERY READER OF A RUN DIRECTORY TAKES ONE RUN ID, AND TAKES IT BY NAME
    ORDER: `report.run_id_of` and `calibration._run_id` both pick
    `sorted(glob("*.arms.jsonl"))[0]`. Any run with no `--out` writes into the
    DEFAULT directory — `runs/<today>/v5-live-<tier>` — under a FRESH uuid, so
    two ids end up side by side whenever one tier is run twice in a day: a
    `--resume` into the directory being resumed (how this was found) and two
    ordinary runs alike. The readers then take the alphabetically first: the new run's
    hops, judge file and meta are on disk and read by nothing, while its arm
    rows ARE merged in (`records.merged_v5_records` globs every file), so every
    case of the new run reads as hopless and the report is a mixture of two
    measurements under one header.

    A pure reader rather than a raise, so `test_harness` can drive it without
    a temp run: `main` prints and exits 2.
    """
    if not run_dir.exists():
        return ()
    suffix = ".arms.jsonl"
    return tuple(sorted({path.name[: -len(suffix)] for path in run_dir.glob(f"*{suffix}")}
                        - {run_id}))


def ladder_digest(path: Path) -> str:
    """`corpus_sha256` лестницы — для строки реестра.

    Отсутствующий файл — пустая строка, а НЕ отказ: реестр ПОМЕЧАЕТ прогон,
    а отказывать прогону из-за несовпадения дайджеста — это §6.1 дисциплины и
    другой файл. Заводить здесь второе место, где прогон может не начаться,
    значит иметь два правила о том, когда числа привязываются к коммиту.
    """
    if not path.exists():
        return ""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise HarnessError(f"{path}: лестница — не объект, а {type(raw).__name__}")
    return str(raw.get("corpus_sha256") or "")


@dataclass(frozen=True)
class RunContext:
    """Всё, что о прогоне известно ДО первого доллара.

    Существует ради одного: строка реестра пишется из ДВУХ мест — из конца
    прогона и из обработчика падения (§1.2: «при завершении И при прерывании»),
    и пятнадцать одинаковых аргументов, выписанных дважды, расходятся на первой
    же правке. Здесь они выписаны один раз, а различаются только те пять,
    которые к моменту записи и правда разные.
    """

    run_id: str
    run_dir: Path
    runs_path: Path
    started_at: str
    tier: str
    cases: int
    repeats: int
    model: str
    judge_model: str
    concurrency: int
    digest: str
    ladder_digest: str
    label: str
    note: str
    ceiling_usd: float
    # §6.1 ОДНОЙ СТРОКОЙ, ИЗВЕСТНОЙ ДО ПЕРВОГО ДОЛЛАРА (`build.worktree_line`).
    # Раньше реестр читал её из `meta.json` — и получал пусто на прерванном
    # прогоне, потому что `meta.json` пишется в конце, а прерванный конца не
    # видит. Именно у прерванного прогона вопрос «к какому дереву его привязать»
    # и стоит: он потратил деньги и объяснить их больше нечем.
    worktree: str
    # §4.1 и §4.2 — ТО ЖЕ САМОЕ, ЧТО УЕЗЖАЕТ В `meta.json`, и из того же места.
    # ТЗ просит цены и шлюз в обоих файлах: каталог прогона стирают и переносят,
    # реестр остаётся в репозитории, и строка, по которой нельзя переоценить
    # прогон в сегодняшних деньгах, через год не значит почти ничего.
    provider: dict[str, object]
    gateway: dict[str, object]
    # ЗНАЧЕНИЯ ВЫБРАННЫХ СЛУЧАЕВ — не для того, чтобы их записать, а для того,
    # чтобы их вычистить: вердикт прерванного прогона несёт текст исключения,
    # то есть всё, что попало в сообщение об ошибке (§1.2, `runinfo.scrub_record`).
    corpus_values: frozenset[str]


def register_run(context: RunContext, state: str, triples_done: int, transport_terminated: int,
                 spent_usd: float, wall_s: float, verdict: str) -> None:
    """Одна строка в `runs.json` (§1.2), из объекта, собранного до старта.

    ВЫЧИСТКА СТОИТ ЗДЕСЬ, В ЕДИНСТВЕННОМ ПИСАТЕЛЕ СТРОКИ, а не на каждом из
    двух концов прогона: свободный текст приезжает в строку и из вердикта
    отчёта, и из текста исключения, и запрет, написанный на одном конце,
    существовал бы только для него. Вычистка, а не отказ, — потому что отказ
    на этом конце стирает строку прогона, который уже заплатил.
    """
    row, removed = runinfo.scrub_record(runinfo.RunRecord(
        run_id=context.run_id, benchmark=BENCHMARK, started=context.started_at,
        finished=runinfo.utc_now(), state=state, tier=context.tier, cases=context.cases,
        repeats=context.repeats, triples_done=triples_done,
        transport_terminated=transport_terminated, model=context.model,
        judge_model=context.judge_model, concurrency=context.concurrency,
        corpus_digest=context.digest, ladder_digest=context.ladder_digest,
        label=context.label, note=context.note, ceiling_usd=context.ceiling_usd,
        spent_usd=spent_usd, wall_s=wall_s, verdict=verdict, worktree=context.worktree,
        run_dir=str(context.run_dir), provider=dict(context.provider),
        gateway=dict(context.gateway)), context.corpus_values)
    if removed:
        print(f"строка реестра вычищена: {'; '.join(removed)}", file=sys.stderr, flush=True)
    runinfo.append_run(context.runs_path, row)


def register_interrupted(context: RunContext, started: float, broken: BaseException) -> None:
    """Строка реестра для прогона, который потратил деньги и не доехал (§1.2).

    ИМЕНОВАННАЯ ФУНКЦИЯ, А НЕ ТЕЛО `except`, по двум причинам. Она считает
    потраченное ПО ТОМУ, ЧТО ЛЕГЛО НА ДИСК (строки троек писались по одной перед
    следующей тройкой, поэтому файл — это и есть всё, за что прогон успел
    заплатить), и это утверждение можно проверить без модели и без денег. И она
    не имеет права уронить сама себя: отказ реестра — сломанный файл, дубль
    `run_id` — подменил бы собой настоящую причину падения, а причина дороже.
    Поэтому свой отказ она печатает и глотает, а исходное исключение продолжает
    лететь у вызывающего.
    """
    partial = written_triples(context.run_dir, context.run_id)
    try:
        register_run(context, state="interrupted", triples_done=len(partial),
                     transport_terminated=0,
                     spent_usd=sum(float(one.get("cost_usd") or 0.0) for one in partial),
                     wall_s=time.time() - started,
                     verdict=f"прогон прерван: {type(broken).__name__}: {broken}")
    except Exception as failed:      # noqa: BLE001 — причина падения дороже этой записи
        print(f"строку реестра записать не удалось ({failed}); прогон {context.run_id} "
              f"остался только каталогом {context.run_dir}", file=sys.stderr, flush=True)


def written_triples(run_dir: Path, run_id: str) -> list[dict[str, object]]:
    """Тройки, уже лежащие на диске. То, что читает обработчик прерывания:
    строки писались по одной перед следующей тройкой, поэтому файл — это и есть
    всё, за что прогон успел заплатить."""
    path = r.run_file(run_dir, run_id, "<run>.triples.jsonl")
    return r.read_rows(path) if path.exists() else []


def gateway_refusal(target: provider.GatewayTarget) -> tuple[str, ...]:
    """Почему `--gateway` отказывает, названное ТЕМ, чего не хватает (ТЗ §4.2).

    ЭТО НЕ «ПЛЕЧО ЕЩЁ НЕ НАПИСАНО». Клиентский путь написан и проверен
    (`provider.HttpGateway` говорит четырьмя эндпойнтами), а упирается пункт 13
    в API ДВИЖКА, и отказ обязан называть именно это — иначе читатель будет
    искать недостающий код у себя, а его там нет.

    ЧЕГО НАБЛЮДАТЕЛЮ НЕ ХВАТАЕТ ПО HTTP, ТРЕМЯ ФАКТАМИ. (1) Хоп — это
    ОТРЕЗОК, ПОДМЕНА И ТИП в каждом сообщении и в каждом результате инструмента
    (`score.Masked.pieces`, из которых собраны `MentionRecord` и
    `ToolResultRecord`); `POST /mask` отвечает только замаскированными
    сообщениями (`pseudex/service.py:667`) и ничего из этого не возвращает.
    (2) Единственный эндпойнт, возвращающий отрезки, — `/spans`, и это НЕ тот
    путь, которым маскировали: он читающий (`vault.peek_token`, ничего не
    чеканит — `pseudex/service.py:471–485`) и берёт хранилище ОРГАНИЗАЦИИ без
    `for_conversation` (`pseudex/service.py:851–853`), так что у строки,
    записанной под каноническим ключом разговора (LINKED-адрес — «The
    conversation scope» в CLAUDE.md), подмены там просто нет. (3) Потоковое
    плечо, которое и СЧИТАЕТСЯ (F3.1), восстанавливает ответ кусками через
    `StreamDetokenizer`; его HTTP-двойник — `/unmask_chunk`, которым
    `provider.HttpGateway` не говорит. Это единственный из трёх пунктов, который
    закрывается здесь, — но закрывать его в одиночку незачем, пока не закрыт (1).

    ЧТО ЗАКРОЕТ ПУНКТ: `/mask` должен возвращать ПРИМЕНЁННЫЕ подмены (отрезок,
    подмена, тип) — тогда плечо по HTTP собирает ту же запись, что и в процессе.
    Это правка поверхности шлюза, то есть отдельная работа по своим правилам
    (skill `api-change`), а не правка бенчмарка.
    """
    return (
        f"--gateway {target.base_url}: отказ. Клиентский путь написан "
        f"(provider.HttpGateway говорит /mask, /unmask, /unmask_arguments, /spans), "
        f"но плечо по HTTP собрать НЕ ИЗ ЧЕГО — не хватает ответа ДВИЖКА, а не кода здесь:",
        "  · POST /mask возвращает только замаскированные сообщения "
        "(pseudex/service.py:667), а наблюдателю нужны применённые подмены: "
        "отрезок, подмена и тип в каждом сообщении и в каждом результате инструмента;",
        "  · /spans отрезки возвращает, но это другой путь: он читающий "
        "(peek_token, ничего не чеканит) и берёт хранилище организации без "
        "for_conversation, поэтому подмены conversation-scoped строки в нём нет;",
        "  · потоковое плечо считается по восстановлению кусками (/unmask_chunk), "
        "которым клиент шлюза не говорит.",
        "Пока /mask не отдаёт применённые подмены, прогон по HTTP записал бы числа, "
        "полученные другим путём, на счёт версии образа — уберите --gateway "
        "(шлюз в процессе) или закройте правку поверхности шлюза (ТЗ §4.2).")


def replay_run(run_dir: Path, baseline: Path) -> list[str]:
    """§4.3 (пункт 14): пересчитать ПЛЕЧИ готового прогона новым наблюдателем —
    без единого вызова модели, без сети, без ключа и без движка.

    ЧТО ИМЕННО ПЕРЕСЧИТЫВАЕТСЯ, И ПОЧЕМУ ЭТОГО НЕ ДЕЛАЛ `--report`. Отчёт
    собирается из `<run>.hops.jsonl` — наблюдений, которые записал ТОТ прогон.
    Когда меняется НАБЛЮДАТЕЛЬ (`observe.py`: новая игла, другое чтение хопа,
    новый статус), отчёт по старым наблюдениям показывает старый прибор на новых
    метриках, и разница читается как движение движка. Здесь хопы считаются
    заново — из `<run>.arms.v5.jsonl` и снимка корпуса, которые прогон уже
    записал, — и только потом собирается отчёт.

    ЭТО И ЕСТЬ КЕШ ОТВЕТОВ МОДЕЛИ В ЕГО РАБОЧЕЙ ФОРМЕ. Всё, что наблюдатель
    читает, — ответы плеча, его вызовы, результаты инструментов и подмены,
    которые модель видела, — уже лежит в записи прогона; `provider.replies_of_run`
    — тот самый читатель, названный в `provider.py` ради этого, и он зовётся
    здесь, чтобы «ни одного вызова» было утверждением о коде, а не о намерении.
    `provider.AnswerCache` остаётся для случая, когда пересчитать надо ПРОМПТ
    (судья с другой рубрикой) — и по правилу пункта 14 живой прогон его не
    читает никогда: `recording` пишет и не читает, `replaying` живёт только на
    этом пути.

    СТРОКИ В РЕЕСТР ЭТОТ ПУТЬ НЕ ПИШЕТ. Реестр — история ПЛАТНЫХ прогонов
    (§1.2); пересчёт не тратит ничего и не создаёт нового прогона, он правит
    наблюдения того же самого. Запись о нём была бы вторым прогоном с теми же
    деньгами в истории.
    """
    run_id = v5_report.run_id_of(run_dir)
    cases, _digest = _load_corpus(run_dir / "corpus.v5.json")
    by_id = {case.base.id: case for case in cases}
    # ПЛЕЧИ, КОТОРЫЕ ПРОГОН ЗАПИСАЛ, — ЧЕРЕЗ ЧИТАТЕЛЯ, НАЗВАННОГО РАДИ ЭТОГО
    # (`provider.replies_of_run`, ТЗ §4.3). Каталог без единого плеча пересчитать
    # нельзя: наблюдателю нечего читать, и пустой файл наблюдений превратил бы
    # отчёт в «н/п» по всем строкам вместо отказа.
    replies = provider.replies_of_run(run_dir)
    if not replies:
        raise HarnessError(
            f"{run_dir}: в <run>.arms.v5.jsonl нет ни одного плеча — пересчитывать нечего")
    records_ = r.merged_v5_records(run_dir)
    hops_path = r.run_file(run_dir, run_id, "<run>.hops.jsonl")
    # СТАРЫЙ ФАЙЛ ЗАМЕЩАЕТСЯ ЦЕЛИКОМ, А НЕ ДОПИСЫВАЕТСЯ: `records.append_row`
    # дописывает по строке, и пересчёт поверх прежних наблюдений дал бы отчёт, в
    # котором каждый хоп посчитан дважды — один раз старым наблюдателем, один
    # новым. И замещается ЧЕРЕЗ СОСЕДНИЙ ФАЙЛ: наблюдатель может упасть на
    # тридцатом случае из тысячи, а каталог платного прогона — единственное, чем
    # эти деньги объяснены; стереть его наблюдения и не дописать новые значило бы
    # потерять прогон ради пересчёта, который ничего не стоил.
    before = len(r.read_rows(hops_path)) if hops_path.exists() else 0
    fresh = hops_path.parent / f"{hops_path.name}.new"
    fresh.unlink(missing_ok=True)
    fresh.touch()
    written = 0
    unknown: list[str] = []
    for row in records_:
        run = r.arm_v5_from_record(row)
        case = by_id.get(run.base.case_id)
        if case is None:
            unknown.append(run.base.case_id)
            continue
        if run.base.termination in EXCLUDED_TERMINATIONS:
            continue
        for hop in observe(case, run, None, None).hops:
            r.append_row(fresh, r.hop_observation_to_json(hop))
            written += 1
    if unknown:
        fresh.unlink(missing_ok=True)
        raise HarnessError(
            f"{run_dir}: плечи называют случаи, которых нет в снимке корпуса "
            f"({sorted(set(unknown))[:3]}): пересчёт молча выбросил бы их из знаменателей")
    # НОЛЬ НАБЛЮДЕНИЙ ТАМ, ГДЕ ОНИ БЫЛИ, — ДЕФЕКТ НАБЛЮДАТЕЛЯ, А НЕ РЕЗУЛЬТАТ.
    # Записанный, он превратил бы отчёт в «н/п» по всем строкам, и прогон, за
    # который заплачено, перестал бы что-либо измерять.
    if before and not written:
        fresh.unlink(missing_ok=True)
        raise HarnessError(
            f"{run_dir}: наблюдатель не произвёл ни одного хопа там, где их было {before}. "
            f"Прежние наблюдения не тронуты — разберитесь в observe.py и повторите")
    fresh.replace(hops_path)
    lines = [f"пересчёт наблюдателя: {len(replies)} плеч, хопов {before} → {written} "
             f"(ни одного вызова модели, ТЗ §4.3)"]
    return lines + finish_run(run_dir, baseline)


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
    # СРЕЗ — ТРЕТИЙ СПОСОБ ВЫБРАТЬ СЛУЧАИ, и он существует потому, что первых
    # двух не хватало ни на один вопрос вида «а как оно на чате». `--ids`
    # требует выписать сто двадцать имён руками (и через месяц никто не скажет,
    # по какому правилу они выписаны), `--tier` даёт только замороженные шесть.
    # Срез — это ПРАВИЛО, записанное в имя прогона, поэтому он повторяем словом,
    # а не списком.
    parser.add_argument("--slice", default="",
                        help=f"срез вместо яруса: {corpus_build.SLICE_AND.join(f'{one}=…' for one in corpus_build.SLICE_AXES)}; "
                             f"несколько значений одной оси — через {corpus_build.SLICE_ANY!r}. "
                             f"Пример: --slice register=chat --slice-size 120")
    parser.add_argument("--slice-size", type=int, default=0,
                        help="сколько случаев взять из среза; 0 — все")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--ceiling", type=float, default=12.0, help="потолок на прогон, USD")
    parser.add_argument("--model", default=AGENT_MODEL)
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument('--agent-connector', choices=('claude', 'deepseek'), default='claude')
    parser.add_argument('--judge-connector', choices=('claude', 'codex'), default='claude')
    parser.add_argument('--agent-effort', choices=('low', 'medium', 'high'), default='low')
    parser.add_argument('--judge-effort', choices=('low', 'medium', 'high'), default='medium')
    parser.add_argument('--connector-max-tokens', type=int, default=60000,
                        help='observed cumulative tokens per session; one in-flight response may overshoot')
    parser.add_argument('--agent-turn-limit', type=int, default=12,
                        help='historical name: total DeepSeek Responses requests across agent sessions')
    parser.add_argument('--max-calls', type=int, default=DEFAULT_MAX_CALLS,
                        help='per-conversation tool-call budget: the loop guard a long chain '
                             'must not trip, generous but bounded')
    parser.add_argument('--judge-request-limit', type=int, default=2)
    parser.add_argument('--codex-home', default=os.environ.get('AGENTPII5_CODEX_HOME', ''),
                        help='dedicated clean CODEX_HOME for the subscription judge')
    parser.add_argument("--no-judge", action="store_true")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--out", default="")
    parser.add_argument("--report", default="", help="пересобрать отчёт из файлов: без модели и без трат")
    parser.add_argument("--replay", default="",
                        help="каталог готового прогона: пересчитать хопы НОВЫМ наблюдателем "
                             "и отчёт — без единого вызова модели (ТЗ §4.3)")
    parser.add_argument("--resume", default="", help="каталог прерванного прогона")
    parser.add_argument("--baseline", default="", help="каталог прогона v4 для колонки сравнения")
    parser.add_argument("--label", default="",
                        help="метка прогона: обязательна для всего, что дороже nano")
    parser.add_argument("--note", default="", help="свободная заметка прогона")
    parser.add_argument("--dry-run", action="store_true",
                        help="оценка случаев, вызовов, токенов, цены и времени; ничего не тратится")
    parser.add_argument("--runs", default=str(runinfo.RUNS_PATH),
                        help="реестр прогонов (runs.json)")
    parser.add_argument("--retries", type=int, default=runinfo.RETRY_ATTEMPTS,
                        help="попыток на случай при флаки-отказе провайдера")
    parser.add_argument("--retry-delay", type=float, default=runinfo.RETRY_BASE_S,
                        help="первый отступ между попытками в секундах (растёт "
                             "экспоненциально до потолка)")
    parser.add_argument("--timeout-scale", type=float, default=1.0,
                        help="множитель per-case таймаута: (120 + 30 * ходов) * scale, "
                             "scale > 0. Для длинных цепочек, которым не хватает "
                             "дефолтных секунд на глубокое рассуждение")
    parser.add_argument("--no-price-brake", action="store_true",
                        help="не вооружать стоп-кран по цене: точечный перепрогон "
                             "дорогих кейсов, чья оценка взята от дешёвой пары и врёт")
    parser.add_argument("--dirty-ok", action="store_true",
                        help="прогон нельзя привязать к коммиту; это записано "
                             "в meta.json и в реестре")
    parser.add_argument("--provider", default="",
                        help=f"{', '.join(provider.PROVIDERS)}; пусто — {provider.PROVIDER_ENV} "
                             f"или anthropic")
    parser.add_argument("--gateway", default="",
                        help="http://host:port — путь клиента; пусто = шлюз в процессе")
    parser.add_argument("--image-digest", default="",
                        help="дайджест образа за --gateway, для сравнения версий")
    args = parser.parse_args()
    if args.agent_connector == 'deepseek' and args.model == AGENT_MODEL:
        parser.error('--agent-connector deepseek requires an explicit --model')
    if args.judge_connector == 'codex' and args.judge_model == JUDGE_MODEL:
        parser.error('--judge-connector codex requires an explicit --judge-model')
    if args.agent_connector == 'deepseek' and args.provider != 'deepseek':
        parser.error('--agent-connector deepseek requires --provider deepseek')
    if args.judge_connector == 'codex' and not args.no_judge and not args.codex_home:
        parser.error('--judge-connector codex requires --codex-home or AGENTPII5_CODEX_HOME')
    if min(args.connector_max_tokens, args.agent_turn_limit, args.judge_request_limit,
           args.max_calls) <= 0:
        parser.error('connector limits must be positive')
    if args.retries < 0:
        parser.error('--retries must be >= 0')
    if args.retry_delay < 0:
        parser.error('--retry-delay must be >= 0')
    if args.timeout_scale <= 0:
        parser.error('--timeout-scale must be > 0')
    if args.resume and (args.agent_connector == 'deepseek' or args.judge_connector == 'codex'):
        parser.error('new connector resume is not yet validated; use a fresh output directory')

    # ОБА БЕСПЛАТНЫХ ПУТИ — ДО ВСЕГО ОСТАЛЬНОГО, и оба возвращаются отсюда: ни
    # бандла, ни модели, ни каталога прогона, ни строки в реестре. `--replay`
    # стоит первым, потому что он делает то же, что `--report`, плюс пересчёт
    # наблюдений, и одновременно они не значат ничего.
    if args.replay:
        run_dir = Path(args.replay)
        for line in replay_run(run_dir, Path(args.baseline) if args.baseline else run_dir):
            print(line)
        return 0
    if args.report:
        run_dir = Path(args.report)
        baseline = Path(args.baseline) if args.baseline else run_dir
        for line in finish_run(run_dir, baseline):
            print(line)
        return 0

    everything, digest = _load_corpus(Path(args.corpus))
    by_id = {case.base.id: case for case in everything}
    ladder_path = Path(args.ladder)
    # ТРИ СПОСОБА ВЫБОРА, И ДВА ИЗ НИХ ВМЕСТЕ НЕ ЗНАЧАТ НИЧЕГО. `--ids` называет
    # случаи поимённо, `--slice` — правилом; прогон, получивший оба, измерил бы
    # одно, а записал в реестр другое, и спор пришлось бы решать чтением кода.
    if args.ids and args.slice:
        print("--ids и --slice вместе не значат ничего: назовите случаи или правило",
              file=sys.stderr)
        return 2
    if args.slice_size and not args.slice:
        print("--slice-size без --slice: размер чего? (ярус называет свой размер сам)",
              file=sys.stderr)
        return 2
    if args.slice:
        try:
            clauses = corpus_build.parse_slice(args.slice, everything)
        except corpus_build.SliceError as refused:
            print(str(refused), file=sys.stderr)
            return 2
        try:
            held = corpus_build.held_of(ladder_path)
        except corpus_build.HoldoutUnreadable as refused:
            print(str(refused), file=sys.stderr)
            return 2
        cases = corpus_build.slice_cases(everything, held, clauses, args.slice_size,
                                         corpus_build.SEED)
        tier_name = corpus_build.slice_name(clauses)
        # СРЕЗ — НЕ ЯРУС, И ЭТО ГОВОРИТСЯ ВСЛУХ ДО ТРАТ, а не только в реестре:
        # человек, сравнивший число среза с числом яруса, сравнил два разных
        # корпуса и узнает об этом из отчёта в лучшем случае.
        print(f"срез, не ярус: {tier_name} · {len(cases)} случаев · холдаут исключён · "
              f"состав {corpus_build.tier_sha256([case.base.id for case in cases])[:12]} — "
              f"сравнивать с ярусом нельзя")
    elif args.ids:
        wanted = [one.strip() for one in args.ids.split(",") if one.strip()]
        missing = [one for one in wanted if one not in by_id]
        if missing:
            print(f"нет таких случаев: {missing}", file=sys.stderr)
            return 2
        # ХОЛДАУТ ЧИТАЕТСЯ ОДНИМ СПОСОБОМ, И ТЕПЕРЬ ЭТО ОТКАЗ, А НЕ ОБЕЩАНИЕ В
        # README. `--ids single-023` проходил оценку без единого слова о том, что
        # назван холдаутный случай, и настоящий прогон за $0.45 поставил бы
        # `holdout_touched_at` навсегда: штамп срабатывает ПОСЛЕ выбора и только
        # записывает. Отказ стоит ДО оценки — там же, где отказы по метке и по
        # грязному дереву, — потому что отменить штамп нечем.
        try:
            named_holdout = sorted(corpus_build.held_of(ladder_path).intersection(wanted))
        except corpus_build.HoldoutUnreadable as refused:
            print(str(refused), file=sys.stderr)
            return 2
        if named_holdout:
            print(f"--ids называет {len(named_holdout)} случаев холдаута "
                  f"({named_holdout[:3]}): холдаут читается одним способом — --tier holdout, "
                  f"и это касание ставит holdout_touched_at навсегда",
                  file=sys.stderr)
            return 2
        cases = [by_id[one] for one in wanted]
        tier_name = corpus_build.IDS_SELECTION
    else:
        picked = {one.id for one in tier([case.base for case in everything],
                                         _ladder(ladder_path), args.tier)}
        cases = [case for case in everything if case.base.id in picked]
        tier_name = args.tier
    if not cases:
        print("выборка пуста", file=sys.stderr)
        return 2

    # §1.1 ОЦЕНКА СТРОИТСЯ ДО ВСЕГО, что стоит денег или времени: до бандла, до
    # модели, до каталога прогона. `--dry-run` возвращается отсюда, и тогда на
    # диске не появляется ничего — каталог прогона, созданный «просто посмотреть»,
    # потом читается как прогон, которого не было.
    judge_name = "" if args.no_judge else args.judge_model
    plan = runinfo.estimate(
        runinfo.demand_of(cases, args.repeats),
        runinfo.pick_basis(runinfo.read_runs(Path(args.runs)), BENCHMARK, tier_name,
                           args.model, judge_name),
        sum(v4_harness.cap_usd(case.base) * 3 for case in cases) * args.repeats,
        args.concurrency)
    # judge_prompt may ask once more when the first quote does not stand.
    # Reserve the worst case before spending anything on the agent; otherwise
    # a valid nano can exhaust this connector halfway through its verdicts.
    required_judge_requests = len(cases) * args.repeats * 2
    if args.dry_run:
        if args.agent_connector == 'deepseek' or args.judge_connector == 'codex':
            print(f'connectors: agent={args.agent_connector}, judge={args.judge_connector}; '
                  f'agent request limit={args.agent_turn_limit}, '
                  f'tool-call limit={args.max_calls}, '
                  f'judge request limit={args.judge_request_limit} '
                  f'(worst case {required_judge_requests}); '
                  'subscription quota is separate from USD; token limits are checked after responses')
        for line in runinfo.estimate_lines(plan):
            print(line)
        return 0

    if args.agent_connector == 'deepseek':
        required_turns = sum(sum(message.role == 'user' for message in case.base.messages)
                             for case in cases) * 3 * args.repeats
        if required_turns > args.agent_turn_limit:
            print(f'выборка требует минимум {required_turns} Responses-запросов агента; '
                  f'--agent-turn-limit={args.agent_turn_limit}. Увеличьте лимит явно '
                  'после согласования размера прогона; модели ещё не вызваны.', file=sys.stderr)
            return 2
    if (not args.no_judge and args.judge_connector == 'codex'
            and required_judge_requests > args.judge_request_limit):
        print(f'выборка может потребовать {required_judge_requests} запросов судьи; '
              f'--judge-request-limit={args.judge_request_limit}. Увеличьте лимит явно; '
              'агент и судья ещё не вызваны.', file=sys.stderr)
        return 2

    # §1.3: метка обязательна выше nano — и проверяется ДО трат, потому что
    # «допишу потом» после прогона на $50 не случается.
    if runinfo.label_required(tier_name) and not args.label:
        print(f"ярус {tier_name} дороже {runinfo.FREE_TIER}: нужна --label «зачем этот прогон» "
              f"(через месяц «прогон от {datetime.now().strftime('%d.%m')}» не значит ничего)",
              file=sys.stderr)
        return 2
    # МЕТКА — ЕДИНСТВЕННАЯ ДВЕРЬ, через которую в файл, лежащий в репозитории
    # вечно, может приехать ключ или настоящее значение: её пишет человек по
    # памяти. Отказ до прогона, а не вычистка после.
    #
    # ПРОТИВ ВСЕГО КОРПУСА, А НЕ ПРОТИВ ВЫБОРКИ. Человек пишет метку по памяти о
    # том, что он видел — а видел он и случаи, которых в ЭТОМ прогоне нет:
    # приёмка вписала в `--note` настоящее значение случая long_support-005,
    # запустив `--ids single-001`, и оно легло в реестр дословно. Реестр лежит в
    # репозитории вечно, поэтому вопрос «принадлежит ли значение выборке» здесь
    # не значит ничего: значение холдаутного случая в нём так же недопустимо.
    values = runinfo.corpus_values(everything)
    for field, text in (("--label", args.label), ("--note", args.note)):
        try:
            runinfo.refuse_secrets(text, field)
            runinfo.refuse_corpus_values(text, field, values)
        except runinfo.RunInfoError as refused:
            print(str(refused), file=sys.stderr)
            return 2

    # §4.1 и §4.2: ЧЕМ ОТВЕЧАЛИ И ПРОТИВ ЧЕГО МАСКИРОВАЛИ — до бандла, потому
    # что неизвестная цена и неизвестный шлюз обесценивают числа прогона, а не
    # портятся по ходу. Ни одного сетевого запроса здесь нет: `parse_gateway`
    # разбирает строку, `run_block` читает ИМЕНА переменных окружения.
    try:
        chosen = (provider.Provider('deepseek', 'https://api.deepseek.com',
                                   'AGENTPII5_DEEPSEEK_BASE_URL', ('DEEPSEEK_API_KEY',),
                                   'responses', 'direct Responses API; peak-rate cost estimate')
                  if args.agent_connector == 'deepseek' and args.provider == 'deepseek'
                  else provider.resolve_provider(args.provider, os.environ))
        choices = [provider.resolve_model(chosen, "agent", args.model)]
        if not args.no_judge:
            judge_provider = (provider.Provider('openai', '', '', (), 'codex',
                                                'ChatGPT subscription, not API billing')
                              if args.judge_connector == 'codex' else
                              provider.resolve_provider('anthropic', os.environ))
            choices.append(provider.resolve_model(judge_provider, "judge", args.judge_model))
        target = provider.parse_gateway(
            args.gateway or os.environ.get(provider.GATEWAY_ENV, ""), args.image_digest)
    except provider.ProviderError as refused:
        print(str(refused), file=sys.stderr)
        return 2
    # ЗАПИСЬ НЕ ИМЕЕТ ПРАВА НАЗЫВАТЬ ТО, ЧЕГО НЕ БЫЛО. Плечи идут через
    # `claude_agent_sdk` (Anthropic) и через шлюз В ЭТОМ ЖЕ ПРОЦЕССЕ; пока это
    # так, прогон с чужим провайдером или с адресом контейнера приписал бы свои
    # числа модели, которая не отвечала, и образу, который ничего не маскировал.
    # Отказ, а не молчаливое «как раньше»: `provider.HttpGateway` и
    # `probe_gateway` уже написаны и ждут ровно одной правки — плеча,
    # которое их позовёт.
    if chosen.name != SDK_PROVIDER and args.agent_connector == 'claude':
        print(f"провайдер {chosen.name!r} объявлен, а плечи зовут модель через "
              f"claude_agent_sdk ({SDK_PROVIDER}): запись назвала бы модель, которая не "
              f"отвечала. Уберите --provider/{provider.PROVIDER_ENV} или дождитесь плеча "
              f"через provider.call_model (ТЗ §4.1)", file=sys.stderr)
        return 2
    if args.agent_connector == 'deepseek' and chosen.name != 'deepseek':
        print('DeepSeek agent requires --provider deepseek', file=sys.stderr)
        return 2
    if target.mode != "inprocess":
        for line in gateway_refusal(target):
            print(line, file=sys.stderr)
        return 2
    if args.image_digest and target.mode == "inprocess":
        print("--image-digest без --gateway: в процессе маскирует исходное дерево, "
              "а не образ — дайджест в записи был бы неправдой", file=sys.stderr)
        return 2
    for one in choices:
        if one.price is None:
            print(f"ВНИМАНИЕ {one.role}: {one.unpriced_reason}", file=sys.stderr)

    # §6.1: ГРЯЗНОЕ ДЕРЕВО И ЧУЖОЙ КОРПУС — тоже до бандла и до модели. Числа,
    # которые не к чему привязать, стоят ровно столько же денег, сколько
    # привязанные. `ladder_path` посчитан один раз выше — выбор случаев и это
    # место обязаны читать ОДНУ лестницу.
    # ВЕСЬ КОРПУС И ВЫБОРКА — ДВА РАЗНЫХ АРГУМЕНТА. Лестница нарисована по всему
    # корпусу и хранит его дайджест; прогон играет ярус. Пока сюда уезжала одна
    # выборка, дайджест ЯРУСА сравнивался с дайджестом КОРПУСА и отказывал
    # каждому живому прогону, кроме `--tier max`, с причиной «корпус не тот».
    provenance = corpus_build.run_provenance(everything, cases, tier_name, ladder_path,
                                             corpus_build.REPO, args.dirty_ok)
    refusals = corpus_build.start_refusals(provenance)
    if refusals:
        for refusal in refusals:
            print(refusal, file=sys.stderr)
        return 2

    load_dev_bundle()
    detector = Detector()
    run_id = str(uuid.uuid4())
    out = Path(args.out) if args.out else (here.parent / "runs" / datetime.now().strftime("%Y-%m-%d")
                                           / f"v5-live-{tier_name}")
    out.mkdir(parents=True, exist_ok=True)
    # BEFORE `write_corpus`, which would overwrite the resumed run's own
    # snapshot of the corpus — the file `--report` replays against.
    # ON EVERY RUN, NOT ONLY ON `--resume`. The default `--out` is
    # `runs/<today>/v5-live-<tier>`, which two ordinary runs of one tier on one
    # day share without either of them saying `--resume` — and then every
    # reader takes the alphabetically first id while `merged_v5_records` globs
    # both. The guard was gated on the flag because that is the path the defect
    # was FOUND on, which is not the same as the path it lives on.
    foreign = foreign_run_ids(out, run_id)
    if foreign:
        print(f"{out} уже содержит прогон(ы) {', '.join(foreign)}: второй идентификатор в "
              f"одном каталоге читатели не различают (report.run_id_of и calibration._run_id "
              f"берут первый по имени). Пишите в СВОЙ каталог: --out <новый каталог>",
              file=sys.stderr)
        return 2
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
    arms: ArmConnector = ClaudeArms(args.timeout_scale)
    if args.agent_connector == 'deepseek':
        arms = ConnectedArms(DeepSeekConnector(DeepSeekSettings(
            args.model, args.agent_effort, args.connector_max_tokens,
            args.agent_turn_limit, deepseek_max_output_tokens(args.connector_max_tokens),
            out / f'{run_id}.agent.usage.jsonl',
            os.environ.get('AGENTPII5_DEEPSEEK_BASE_URL', 'https://api.deepseek.com'))),
            args.max_calls, args.timeout_scale)
    if config is not None and args.judge_connector == 'codex':
        config = ConnectedJudgeConfig(
            model=args.judge_model, ledger=ledger, query_cap_usd=QUERY_CAP_USD,
            retries=RETRIES, trace_path=config.trace_path, temperature=JUDGE_TEMPERATURE,
            connector=CodexJudgeConnector(CodexSettings(
                args.judge_model, args.judge_effort, args.connector_max_tokens,
                args.judge_request_limit, out / f'{run_id}.judge.usage.jsonl',
                Path(args.codex_home))))
    sampling = (f'effort={args.judge_effort}; temperature не задаётся' if args.judge_connector == 'codex'
                else f't={JUDGE_TEMPERATURE}')
    print(f"прогон {run_id} · агент {args.model} · судья "
          f"{'—' if args.no_judge else args.judge_model} ({sampling}) · "
          f"промпт {prompt_sha256()[:12]} · "
          f"{len(cases)} случаев × K={args.repeats} × 3 плеча · потолок ${args.ceiling:.2f}"
          + (f" · метка «{args.label}»" if args.label else ""), flush=True)
    for line in runinfo.estimate_lines(plan):
        print(line, flush=True)
    # ОЖИДАНИЕ НА СЛУЧАЙ ДЛЯ СТОП-КРАНА — точка оценки, делённая на тройки.
    # Ноль, когда оценки не было: кран не вооружён, и это сказано вслух, а не
    # срабатывает наугад на первом же прогоне новой пары моделей.
    expected = (0.0 if args.no_price_brake else
                (plan.usd_point / plan.demand.triples
                 if plan.basis.kind != "reserve_only" and plan.demand.triples else 0.0))
    brake_line = ("не вооружён (оценки нет)" if expected <= 0.0 else
                  f"${expected * runinfo.COST_BRAKE_FACTOR:.4f} на случай в среднем")
    print(f"стоп-кран по цене: {brake_line}", flush=True)
    recorded = provider.run_block(chosen, choices, target, os.environ)
    if args.agent_connector == 'deepseek' or args.judge_connector == 'codex':
        recorded['provider']['connectors'] = {  # type: ignore[index]
            'agent': args.agent_connector, 'judge': args.judge_connector,
            'sdk': 'openai==3.19.2; openai-agents==0.22.3; openai-codex==0.157.1',
            'agent_effort': args.agent_effort,
            'judge_effort': args.judge_effort, 'max_tokens': args.connector_max_tokens,
            'agent_turn_limit': args.agent_turn_limit, 'judge_request_limit': args.judge_request_limit,
            'max_calls': args.max_calls,
            # The multiplier that decided the per-case deadline (the excluded
            # `timeout` arms are reproduced only if this number is known).
            'timeout_scale': args.timeout_scale,
            'agent_cost_basis': ('deepseek_peak_estimate_2026-09-26' if args.agent_connector == 'deepseek'
                                 else 'claude_sdk_reported_usd'),
            'judge_cost_basis': ('chatgpt_subscription_quota_not_api_usd' if args.judge_connector == 'codex'
                                 else 'claude_sdk_reported_usd'),
            'temperature': 'not configurable by Codex; legacy temperature field is not measured'}
    context = RunContext(
        run_id=run_id, run_dir=out, runs_path=Path(args.runs), started_at=runinfo.utc_now(),
        tier=tier_name, cases=len(cases), repeats=args.repeats, model=args.model,
        judge_model=judge_name, concurrency=args.concurrency, digest=digest,
        ladder_digest=ladder_digest(ladder_path), label=args.label, note=args.note,
        ceiling_usd=args.ceiling, worktree=corpus_build.worktree_line(provenance),
        # ОДИН ОБЪЕКТ НА ДВА ФАЙЛА: `meta.json` и строка реестра получают тот же
        # блок из того же вызова. Собранный дважды, он однажды разошёлся бы, и
        # тогда два файла об одном прогоне спорили бы о том, что отвечало.
        provider=dict(recorded["provider"]),          # type: ignore[arg-type]
        gateway=dict(recorded["gateway"]),            # type: ignore[arg-type]
        corpus_values=values)
    # §3.2: ХОЛДАУТ ШТАМПУЕТСЯ ДО ПЕРВОГО ВЫЗОВА, а не по завершении. Прогон,
    # прерванный на середине, УЖЕ показал эти случаи модели; отметка, которую
    # ставит только дошедший до конца, оставила бы холдаут «нетронутым» после
    # того, как по нему отладились. Первое касание — то, которое считается:
    # `stamp_holdout_touched` возвращает уже стоящую отметку и ничего не пишет.
    if corpus_build.touches_holdout(ladder_path, [case.base.id for case in cases]):
        touch = corpus_build.stamp_holdout_touched(ladder_path, run_id, context.started_at)
        print(f"холдаут прочитан живым прогоном {touch.touched_by[:12]} от "
              f"{touch.touched_at}: состав ярусов больше не перерисовывается (R-52, п.10)",
              flush=True)
    policy = DrivePolicy(attempts=max(1, args.retries), base_s=args.retry_delay,
                         pause=asyncio.sleep, jitter=random.random,
                         expected_per_case_usd=expected, timeout_scale=args.timeout_scale)
    started = time.time()
    # §1.2: ОДНА ЗАЩИЩЁННАЯ ОБЛАСТЬ НА ВСЁ, ЧТО ИДЁТ ПОСЛЕ ПЕРВОГО ДОЛЛАРА, а не
    # на один `asyncio.run`. Раньше обработчик накрывал только сам прогон, и
    # любое падение ПОСЛЕ него — сборка отчёта, запись `meta.json`, чтение
    # вердикта — оставляло реестр без строки; то есть прогон, который заплатил
    # за все тройки и упал на последнем шаге, был неотличим от прогона, которого
    # не было. Деньги тратит `drive_v5`, поэтому область начинается на нём и
    # кончается там, где строка уже записана.
    registered = False
    try:
        outcome = asyncio.run(drive_v5(cases, args.repeats,
                                       triple_runner(detector, ledger, config, args.model, run_id, arms),
                                       out, run_id, args.concurrency, already, policy))
        triples = outcome.triples
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
        wall_s = time.time() - started
        print(f"\nпотрачено ${spent:.2f} из ${args.ceiling:.2f} "
              f"(судья ${judged:.2f}) за {wall_s:.0f}s · "
              f"нераскрытых подмен в ходах: {residual_turns}")
        # §1.4: снятые обрывом — отдельной строкой, а не внутри «исключено»: это
        # единственная строка отчётности, отличающая «провайдер оборвался» от
        # «плечо не доиграло», и без неё прогон с тридцатью обрывами читается как
        # прогон с тридцатью дефектами агента.
        if outcome.transport_terminated:
            print(f"снято обрывом провайдера ({runinfo.TRANSPORT_TERMINATED}): "
                  f"{outcome.transport_terminated} — из знаменателей исключены")
        # §1.1: оценка против факта. Без этой строки никто не узнает, что оценка
        # врёт вдвое, а следующий прогон построится на ней же.
        for line in runinfo.actual_lines(plan, spent, wall_s):
            print(line)
        # НЕ ОТКАЛИБРОВАН until a calibration file says otherwise: silence about
        # the judge is «неизвестно», never «годен».
        stamp_judge_file(out, run_id, CalibrationStamp(
            judge_model="" if args.no_judge else args.judge_model, prompt_sha256=prompt_sha256(),
            n=0, raw_agreement=0.0, kappa=0.0, per_type_kappa={}, repeat_disagreement=1.0,
            calibrated=False))
        write_meta(out, run_id, model=args.model,
                   judge_model="" if args.no_judge else args.judge_model, tier=tier_name,
                   repeats=args.repeats, digest=digest, ceiling_usd=args.ceiling, spent_usd=spent,
                   label=args.label, note=args.note, started=context.started_at, wall_s=wall_s,
                   extra={"worktree": context.worktree,
                          "provenance": corpus_build.provenance_json(provenance),
                          "provider": context.provider, "gateway": context.gateway})
        # Шапку отчёта рисует `report.render`, и с этого захода она печатает метку,
        # заметку и состояние дерева сама — из `meta.json`, который лежит рядом с
        # отчётом и уезжает вместе с ним. Второй строки здесь больше нет: два места,
        # печатающие одно, расходятся ровно тогда, когда одно из них правят.
        for line in finish_run(out, Path(args.baseline) if args.baseline else out):
            print(line)
        # §1.2: строка реестра — ПОСЛЕ отчёта, потому что вердикт полноты читается
        # из `<run>.gate.json`, который пишет отчёт.
        verdict = runinfo.verdict_of(out, run_id)
        if outcome.stopped:
            verdict = f"{verdict}; остановлен стоп-краном по цене"
        register_run(context, state="interrupted" if outcome.stopped else "finished",
                     triples_done=len(triples), transport_terminated=outcome.transport_terminated,
                     spent_usd=spent, wall_s=wall_s, verdict=verdict)
        registered = True
    except BaseException as broken:
        # Исключение летит дальше: прерванный прогон не притворяется завершённым.
        # `registered` — на случай падения В САМОЙ записи строки: второй заход с
        # тем же `run_id` реестр отвергнет (он аддитивен), и этот отказ подменил
        # бы собой настоящую причину.
        if not registered:
            register_interrupted(context, started, broken)
        raise
    print(f"\nкаталог прогона: {out}")
    print(f"реестр: {args.runs} · строка {run_id[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
