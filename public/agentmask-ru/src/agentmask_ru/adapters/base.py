"""The adapter interface: one method, two shapes of masker.

A masker is either TWO-PHASE — the caller asks it to mask, decides what the
model would answer, then asks it to restore (Presidio, LLM Guard, our
sidecar, any library) — or a PROXY that does both inside one HTTP request
and never hands the masked text to the caller at all (Cloud.ru's Go filter,
LiteLLM, our own proxy leg). A protocol with `mask()` and `restore()` cannot
express the second, so the interface is inverted: the harness passes in the
DECISION FUNCTION and the adapter calls it with whatever the model would
see.

    session.run_turn(messages, tools, decide) -> TurnResult

Two-phase adapters inherit `run_turn` from `TwoPhaseSession` below and
implement `mask` and `restore_arguments`. Proxy adapters implement
`run_turn` themselves.

AN ERROR IS AN OUTCOME, NEVER A SKIP. A masker that returns 503, times out
or hands back malformed JSON has failed the turn, and the report says so
with the reason; dropping the case would flatter it.
"""

import json
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True)
class MaskedView:
    """What the model is shown for one turn."""

    messages: list[dict[str, object]]
    tools: list[dict[str, object]]


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: str          # a JSON object, as a model emits it


@dataclass(frozen=True)
class ModelReply:
    text: str | None
    tool_call: ToolCall | None


Decide = Callable[[MaskedView], ModelReply]


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    type: str


@dataclass(frozen=True)
class TurnResult:
    masked: MaskedView | None           # None when the adapter never exposes it
    reply: ModelReply | None
    restored_arguments: str | None      # what the tool received, after restoration
    error: str | None


class Session(Protocol):
    """One conversation. A stateful masker may keep a mapping here; a
    per-request one keeps nothing and that difference is what the
    consistency line measures."""

    def run_turn(self, messages: list[dict[str, object]], tools: list[dict[str, object]], decide: Decide) -> TurnResult:
        ...

    def spans(self, text: str) -> list[Span] | None:
        """Typed spans, when the masker exposes them; None when it does not.
        A masker that only returns masked text is scored on the type-blind
        line and printed as «types not exposed», never as a zero."""
        ...

    def close(self) -> None:
        ...


class Masker(Protocol):
    name: str
    config: dict[str, object]           # goes verbatim into the run manifest

    def open(self, case_id: str) -> Session:
        ...


class TwoPhaseSession:
    """Base for maskers the harness can call directly: mask, then restore."""

    def mask(self, messages: list[dict[str, object]], tools: list[dict[str, object]]) -> MaskedView:
        raise NotImplementedError

    def restore_arguments(self, arguments: str) -> str:
        raise NotImplementedError

    def spans(self, text: str) -> list[Span] | None:
        return None

    def close(self) -> None:
        return None

    def run_turn(self, messages: list[dict[str, object]], tools: list[dict[str, object]], decide: Decide) -> TurnResult:
        try:
            masked = self.mask(messages, tools)
        except Exception as exc:  # noqa: BLE001 — the adapter's failure is the measurement
            return TurnResult(masked=None, reply=None, restored_arguments=None, error=f"mask failed: {exc}")
        reply = decide(masked)
        if reply.tool_call is None:
            return TurnResult(masked=masked, reply=reply, restored_arguments=None, error=None)
        try:
            restored = self.restore_arguments(reply.tool_call.arguments)
        except Exception as exc:  # noqa: BLE001
            return TurnResult(masked=masked, reply=reply, restored_arguments=None, error=f"restore failed: {exc}")
        return TurnResult(masked=masked, reply=reply, restored_arguments=restored, error=None)


def parse_arguments(arguments: str) -> dict[str, str] | None:
    """A tool call whose arguments do not parse is a broken call — the
    commonest way a placeholder restore breaks is by splicing a value with a
    quote in it straight into the JSON."""
    try:
        parsed = json.loads(arguments)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return {str(k): v if isinstance(v, str) else json.dumps(v, ensure_ascii=False) for k, v in parsed.items()}
