"""Inline masking receipts, captured at the splice, never inferred from output.

Offsets are half-open Unicode codepoint offsets in one wire string field (JSON
arguments stay a string, not a second decoded document). Cached snapshots contain
only shown text and coordinates, never source literals. Request identity and JSON
Pointers are attached outside the cache, so identical content in two fields still
has two occurrences. This is a receipt of this transformation, not detection
coverage and not a reconstruction of earlier requests.
"""

from dataclasses import dataclass
import hashlib
import uuid
from typing import Literal


@dataclass(frozen=True)
class Edit:
    start: int
    end: int
    shown: str
    entity_type: str
    base_token: str | None = None
    kind: Literal["pseudonym", "redaction"] = "pseudonym"


@dataclass(frozen=True)
class Replacement:
    source_start: int
    source_end: int
    output_start: int
    output_end: int
    entity_type: str
    shown: str
    base_token: str | None
    kind: Literal["pseudonym", "redaction"]


@dataclass(frozen=True)
class MaskedText:
    text: str
    replacements: tuple[Replacement, ...] = ()
    complete: bool = True


def snapshot(text: str, edits: list[Edit]) -> MaskedText:
    """Record the edits a single splice chose; no value search is involved."""
    shift = 0
    replacements = []
    for edit in sorted(edits, key=lambda one: one.start):
        start = edit.start + shift
        replacements.append(Replacement(
            edit.start, edit.end, start, start + len(edit.shown),
            edit.entity_type, edit.shown, edit.base_token, edit.kind))
        shift += len(edit.shown) - (edit.end - edit.start)
    return MaskedText(text, tuple(replacements))


@dataclass(frozen=True)
class _Piece:
    length: int
    source_start: int | None
    source_end: int | None
    replacement: Edit | None = None


def _cut(piece: _Piece, start: int, end: int) -> _Piece:
    if start == 0 and end == piece.length:
        return piece
    if piece.replacement is None and piece.source_start is not None:
        return _Piece(end - start, piece.source_start + start, piece.source_start + end)
    # A partial cut through a non-linear replacement has no exact source
    # coordinate. Do not pretend proportional offsets are evidence.
    return _Piece(end - start, None, None, piece.replacement)


class Trace:
    """Request-local coordinate tape across reserve, mask, splice and echo.

    Only live text is held here. A tape is discarded after emitting a frozen
    snapshot; it is never stored on a shared vault or in the content cache.
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.pieces = [_Piece(len(text), 0, len(text))] if text else []
        self.complete = True

    def _range(self, start: int, end: int) -> list[_Piece]:
        out = []
        at = 0
        for piece in self.pieces:
            stop = at + piece.length
            lo, hi = max(start, at), min(end, stop)
            if lo < hi:
                out.append(_cut(piece, lo - at, hi - at))
            at = stop
        return out

    def apply(self, text: str, edits: list[Edit]) -> None:
        """Compose only explicitly supplied splice operations, not a diff."""
        out = []
        written = []
        cursor = 0
        for edit in sorted(edits, key=lambda one: one.start):
            if not (cursor <= edit.start < edit.end <= len(self.text)):
                raise ValueError("invalid inspection splice coordinates")
            out.extend(self._range(cursor, edit.start))
            written.extend((self.text[cursor:edit.start], edit.shown))
            consumed = self._range(edit.start, edit.end)
            exact = bool(consumed) and all(piece.source_start is not None for piece in consumed)
            if exact:
                exact = all(left.source_end == right.source_start
                            for left, right in zip(consumed, consumed[1:]))
            if not exact:
                self.complete = False
            out.append(_Piece(len(edit.shown), consumed[0].source_start if exact else None,
                              consumed[-1].source_end if exact else None, edit))
            cursor = edit.end
        out.extend(self._range(cursor, len(self.text)))
        written.append(self.text[cursor:])
        if "".join(written) != text:
            raise ValueError("inspection splice disagrees with transformation")
        self.pieces, self.text = out, text

    def apply_snapshot(self, masked: MaskedText) -> None:
        self.complete = self.complete and masked.complete
        self.apply(masked.text, [Edit(one.source_start, one.source_end, one.shown,
                                     one.entity_type, one.base_token, one.kind)
                                 for one in masked.replacements])

    def freeze(self) -> MaskedText:
        out = []
        at = 0
        complete = self.complete
        for piece in self.pieces:
            end = at + piece.length
            edit = piece.replacement
            if edit is not None and edit.entity_type:
                if piece.source_start is None:
                    complete = False
                else:
                    out.append(Replacement(piece.source_start, piece.source_end, at, end,
                                           edit.entity_type, self.text[at:end],
                                           edit.base_token, edit.kind))
            at = end
        return MaskedText(self.text, tuple(out), complete)


def pointer(path: str, component: object) -> str:
    return path + "/" + str(component).replace("~", "~0").replace("/", "~1")


class Inspection:
    """One request's receipt builder; never shared between worker threads."""

    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        self.receipt_id = uuid.uuid4().hex
        self._fields: list[tuple[str, MaskedText]] = []

    def record(self, path: str | None, masked: MaskedText) -> None:
        if path is not None:
            self._fields.append((path, masked))

    def payload(self, conversation_id: str, pseudonym_scope: str) -> dict[str, object]:
        replacements = []
        incomplete = []
        for path, masked in self._fields:
            if not masked.complete:
                incomplete.append({"path": path, "reason": "non_linear_overlap"})
            for index, one in enumerate(masked.replacements):
                identity = f"{self.receipt_id}\x00{path}\x00{index}"
                replacements.append({
                    "occurrence_id": hashlib.sha256(identity.encode()).hexdigest()[:32],
                    "path": path,
                    "source_start": one.source_start, "source_end": one.source_end,
                    "output_start": one.output_start, "output_end": one.output_end,
                    "type": one.entity_type, "shown": one.shown,
                    "base_token": one.base_token, "kind": one.kind,
                })
        return {"version": 1, "request_id": self.request_id, "receipt_id": self.receipt_id,
                "conversation_id": conversation_id, "pseudonym_scope": pseudonym_scope,
                "offset_unit": "unicode_codepoint", "complete": not incomplete,
                "limitations": incomplete, "replacements": replacements}


def requested(body: dict) -> tuple[bool, str]:
    """Strict opt-in validation shared by the two /mask deployment shapes."""
    enabled = body.get("inspection", False)
    if not isinstance(enabled, bool):
        raise ValueError("inspection must be a boolean")
    if not enabled:
        return False, ""
    request_id = body.get("request_id")
    if request_id is not None and (not isinstance(request_id, str) or not request_id.strip()
                                   or len(request_id) > 256):
        raise ValueError("request_id must be a non-empty string of at most 256 characters")
    return enabled, request_id if request_id is not None else uuid.uuid4().hex
