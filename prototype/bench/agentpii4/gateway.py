"""The gateway seam: what stands between the conversation and the model.

Two implementations of one protocol. `PassThrough` is the control arm — the
model reads the real text and its tool calls go to the mock untouched.
`RealGateway` is the intervention arm and it takes THE PRODUCTION PATH:
`envelope.mask_messages` / `mask_tools` on the way in, `redact.unmask_arguments`
on every tool call, `redact.unmask_text` on the final reply, and the mock's
result pushed through `mask_messages` before the model sees it.

Lifted from `bench/agentpii3/live/run.py::LiveGateway` with one change of
shape: `push_tool` takes a DYNAMIC result the mock produced, not a scripted
corpus index — v3 had no such path because its tool results were scripted.
The double-pass fail-closed check is kept: every string the model reads is
also masked by `score._mask_message` (the same two functions production
composes, minus cache and audit) and the two must agree byte for byte, or the
arm stops as a harness error. The spans the detection axis counts must
describe the string the model actually read.
"""
import json
import re
from typing import Protocol

from bench.agentpii3 import score
from bench.agentpii4.parts import parts_of
from bench.agentpii4.schema import Case, message_text
from bench.agentpii4.tools import REGISTRY, flatten
from pseudex.audit import AuditLog
from pseudex.detect_all import Detector
from pseudex.envelope import MaskContext, conversation_key, mask_messages, mask_tools
from pseudex.maskcache import MaskCache
from pseudex.redact import residual_tokens, unmask_arguments, unmask_text
from pseudex.vault import Vault

_ORG = "agentpii4"
_AGENT = "bench"


class HarnessError(RuntimeError):
    """The rig, not the product, failed. The arm is excluded, never scored."""


class Gateway(Protocol):
    @property
    def conversation_id(self) -> str: ...
    def tools(self) -> list[dict[str, object]]: ...
    def push_user(self, index: int) -> str: ...
    def push_system(self, text: str) -> str: ...
    def push_tool(self, name: str, text: str) -> str: ...
    def note(self, text: str) -> None: ...
    def note_tool_call(self, name: str, arguments: dict[str, object]) -> None: ...
    def restore_arguments(self, arguments: dict[str, object]) -> tuple[dict[str, object], dict[str, tuple[str, ...]]]: ...
    def restore_text(self, text: str) -> str: ...
    def masked_spans(self) -> dict[int, tuple[tuple[int, int], ...]]: ...
    def substitutes_seen(self) -> dict[str, str]: ...
    def substitutes(self) -> tuple[str, ...]: ...
    @property
    def faults(self) -> tuple[str, ...]: ...


class PassThrough:
    """The control arm: nothing is masked, nothing is restored."""

    def __init__(self, case: Case) -> None:
        self._case = case
        self._conversation = case.conversation_id or "control"

    @property
    def conversation_id(self) -> str:
        return self._conversation

    def tools(self) -> list[dict[str, object]]:
        return [dict(REGISTRY[name].schema) for name in self._case.tools]

    def push_user(self, index: int) -> str:
        return message_text(self._case, index)

    def push_system(self, text: str) -> str:
        return text

    def push_tool(self, name: str, text: str) -> str:
        return text

    def note(self, text: str) -> None:
        return None

    def note_tool_call(self, name: str, arguments: dict[str, object]) -> None:
        return None

    def restore_arguments(self, arguments: dict[str, object]) -> tuple[dict[str, object], dict[str, tuple[str, ...]]]:
        return dict(arguments), {}

    def restore_text(self, text: str) -> str:
        return text

    def masked_spans(self) -> dict[int, tuple[tuple[int, int], ...]]:
        return {}

    def substitutes_seen(self) -> dict[str, str]:
        return {}

    def substitutes(self) -> tuple[str, ...]:
        return ()

    @property
    def faults(self) -> tuple[str, ...]:
        return ()


class RealGateway:
    """One case's masking session on the production path."""

    def __init__(self, case: Case, detector: Detector, vault: Vault, audit: AuditLog,
                 cache: MaskCache) -> None:
        conversation = case.conversation_id or conversation_key(
            [{"role": message.role, "content": message.content} for message in case.messages])
        self._case = case
        self._detector = detector
        self._base = vault
        self._view = vault.for_conversation(conversation)
        self._conversation = conversation
        self._context = MaskContext(detector=detector, vault=self._view, audit=audit,
                                    cache=cache, org_id=_ORG, agent_id=_AGENT,
                                    conversation_id=conversation)
        self._transcript: list[dict[str, object]] = []
        self._masked: dict[int, score.Masked] = {}
        self._tool_results: list[score.Masked] = []
        self._tool_pieces: list[score.Piece] = []
        self._tools: list[dict[str, object]] | None = None
        self._faults: list[str] = []

    @property
    def conversation_id(self) -> str:
        return self._conversation

    @property
    def vault(self) -> Vault:
        return self._base

    def tools(self) -> list[dict[str, object]]:
        if self._tools is not None:
            return self._tools
        raw = [dict(REGISTRY[name].schema) for name in self._case.tools]
        masked = mask_tools(raw, self._context, False)
        if not isinstance(masked, list):
            raise HarnessError("mask_tools вернул не список")
        self._tools = [one for one in masked if isinstance(one, dict)]
        return self._tools

    def _push(self, wire: dict[str, object], text: str, index: int | None) -> str:
        self._transcript.append(wire)
        # The scorer reads the SAME frozen record production's `mask_messages`
        # snapshots at the start of its pass. Observing BEFORE the production
        # mask keeps the scorer's `shown_forms` read free of the values THIS
        # message is about to mint; the scorer only mints tokens (idempotent),
        # so the production pass below sees the same pre-pass record.
        observed = score._mask_message(text, self._detector, self._view,
                                       wire.get("role", ""))
        masked = mask_messages([dict(one) for one in self._transcript], self._context, False)
        content = masked[-1].get("content")
        if not isinstance(content, str):
            raise HarnessError(f"{self._case.id}: mask_messages вернул не строку")
        if observed.masked != content:
            raise HarnessError(
                f"{self._case.id}: маскирование разошлось — производственный путь "
                f"{content[:60]!r}, счётный {observed.masked[:60]!r}")
        if index is not None:
            self._masked[index] = observed
        else:
            self._tool_results.append(observed)
        self._on_masked_request(masked)
        return content

    def _on_masked_request(self, masked: list[dict[str, object]]) -> None:
        """Optional exact request capture at the production mask call."""
        return None

    def push_system(self, text: str) -> str:
        return self._push({"role": "system", "content": text}, text, 0)

    def push_user(self, index: int) -> str:
        text = message_text(self._case, index)
        return self._push({"role": "user", "content": text}, text, index)

    def push_tool(self, name: str, text: str) -> str:
        """A result the MOCK produced, masked before the model reads it."""
        return self._push({"role": "tool", "name": name, "content": text}, text, None)

    def note(self, text: str) -> None:
        self._transcript.append({"role": "assistant", "content": text})

    def note_tool_call(self, name: str, arguments: dict[str, object]) -> None:
        """The assistant turn that carries the call, as the wire carries it. It
        is re-masked with the transcript on the next push, which is production
        behaviour — a substitute the model reshaped is exercised, not hidden."""
        self._transcript.append({"role": "assistant", "content": "", "tool_calls": [
            {"type": "function", "function": {"name": name,
                                              "arguments": json.dumps(arguments, ensure_ascii=False)}}]})

    def restore_arguments(self, arguments: dict[str, object]) -> tuple[dict[str, object], dict[str, tuple[str, ...]]]:
        """Detokenise as the sidecar does — the JSON walk, never a flat replace —
        and report, per leaf, every minted string (whole or piece) that survived."""
        restored = unmask_arguments(json.dumps(arguments, ensure_ascii=False), self._base)
        try:
            parsed = json.loads(restored)
        except json.JSONDecodeError:
            self._faults.append("детокенизация сломала собственный JSON")
            return dict(arguments), {"": ("<broken json>",)}
        if not isinstance(parsed, dict):
            self._faults.append("детокенизация вернула не объект")
            return dict(arguments), {"": ("<not an object>",)}
        residual: dict[str, tuple[str, ...]] = {}
        pieces = self._pieces()
        for path, value in flatten(parsed).items():
            if isinstance(value, str) and value:
                left = tuple(residual_tokens(value, self._base))
                if not left:
                    # A PIECE of a substitute is the engine's own string too.
                    # `residual_tokens` knows whole tokens; a street written on
                    # its own into `address.street` is not one, and it reached
                    # the mock as the fake with an empty residual list.
                    folded = value.casefold()
                    left = tuple(piece for piece in pieces
                                 if folded == piece or (len(piece) >= 4 and re.search(rf"(?<!\w){re.escape(piece)}(?!\w)", folded)))
                if left:
                    residual[path] = left
        return parsed, residual

    def _pieces(self) -> tuple[str, ...]:
        """Every part of every minted substitute this session has shown the
        model, lower-cased; short pieces (a house number) are left out because
        «12» is also a quantity."""
        out: set[str] = set()
        # THE SETTLEMENT INSIDE A SUBSTITUTE IS REAL (vault `_settlement_of`), so
        # the customer's own city is not a piece of ours — counting it would
        # report every «Самара» in a reply as a substitute shown.
        real = {part.casefold() for item in self._case.pii for part in item.parts.values() if part}
        for kind, surface in self._typed_substitutes():
            if kind not in ("LOC", "NAME", "PASSPORT"):
                continue
            for part in parts_of(kind, surface).values():
                if part and len(part) >= 2 and not part.isdigit() and part.casefold() not in real:
                    out.add(part.casefold())
        return tuple(sorted(out))

    def _typed_substitutes(self) -> tuple[tuple[str, str], ...]:
        """(engine type, substitute) for everything minted in this session —
        the type decides how a substitute splits into pieces; a street split as
        a name yields «переулок» as a surname."""
        seen: set[tuple[str, str]] = set()
        for message in list(self._masked.values()) + self._tool_results:
            for piece in message.pieces:
                if piece.substitute.strip():
                    seen.add((piece.engine_type, piece.substitute))
        for piece in self._tool_pieces:
            if piece.substitute.strip():
                seen.add((piece.engine_type, piece.substitute))
        return tuple(sorted(seen))

    def restore_text(self, text: str) -> str:
        return unmask_text(text, self._base)

    def masked_spans(self) -> dict[int, tuple[tuple[int, int], ...]]:
        """Отрезки КАЖДОГО пользовательского сообщения, которые движок замаскировал.

        ОСЬ ПЕРЕМАСКИРОВАНИЯ НЕ СУЩЕСТВОВАЛА В v4 ВООБЩЕ. Корпус умеет носить
        негативы (`Case.negatives` — номер заказа, трек, город как место, а не
        адрес), API для них написан (`common.MessageDraft.negative`), и ни одна
        семья его ни разу не вызвала; скорер v3 для них есть, и v4 его не звал.
        Значит самый частый способ сломать агента — замаскировать то, что ПД не
        является, — не мерился НИЧЕМ. Это половина прибора, а не украшение:
        полноту без точности покупает одна строка «маскировать всё».
        """
        return {index: tuple((piece.start, piece.end) for piece in one.pieces)
                for index, one in self._masked.items()}

    def substitutes_seen(self) -> dict[str, str]:
        """item id -> the substitute string the model read in its place."""
        out: dict[str, str] = {}
        for item in self._case.pii:
            if item.where.kind != "message":
                continue
            masked = self._masked.get(item.where.msg)
            if masked is None:
                continue
            surface = score._seen(masked, item.where.start, item.where.end)
            if surface and surface != item.value:
                out[item.id] = surface
        # Seed items arrive inside tool results; the substitute is whatever
        # piece covered the seed value's text there.
        for masked in self._tool_results:
            for piece in masked.pieces:
                original = masked.text[piece.start:piece.end]
                for item in self._case.pii:
                    if item.where.kind == "seed" and item.id not in out and original == item.value:
                        out[item.id] = piece.substitute
        return out

    def substitutes(self) -> tuple[str, ...]:
        minted = {piece.substitute for message in self._masked.values() for piece in message.pieces}
        minted |= {piece.substitute for message in self._tool_results for piece in message.pieces}
        minted |= {piece.substitute for piece in self._tool_pieces}
        return tuple(sorted(value for value in minted if value.strip()))

    def detection_messages(self) -> dict[int, score.Masked]:
        return dict(self._masked)

    @property
    def faults(self) -> tuple[str, ...]:
        return tuple(self._faults)

    def fault(self, why: str) -> None:
        self._faults.append(why)
