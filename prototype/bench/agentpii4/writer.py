"""The one place a message string is assembled, with offsets laid down as it grows.

THE INVARIANT EVERY v3 FAMILY REPEATS AND v4 ENFORCES IN ONE CLASS: nothing
searches a finished message for a value it already knows it put there. A
searched offset finds the FIRST occurrence, and the finished string is what the
register transform already rewrote — 162 of 183 sloppy failures in v1 were that
bug, twice. `validate.prove_no_search` watches for `str.find` and `re.*` in the
scenario frames; this class is what makes the watch satisfiable.

`Writer.put` records a chunk and, when keyed, its span. Register noise is
applied to the CHUNK before `put`, never to the assembled text. `finish` is
final: a writer refuses to be written after it.

The JSON emitter is lifted from `families/toolresult.py` and reports where it
put each tagged value, so a tool RESULT the mock produces can carry gold spans
for the detection axis.
"""
import json
import unicodedata
from dataclasses import dataclass


class WriterError(ValueError):
    """A message was assembled in a way the corpus may not carry."""


@dataclass(frozen=True)
class TraceRow:
    """One chunk as written: where it went and what produced it."""

    key: str
    start: int
    end: int
    origin: str     # "value:<item id>" | "chunk:<helper name>" | "literal"


class Writer:
    """A message under construction. Not frozen — it IS the mutable state."""

    def __init__(self) -> None:
        self._pieces: list[str] = []
        self._spans: dict[str, tuple[int, int]] = {}
        self._trace: list[TraceRow] = []
        self._length = 0
        self._done = False

    def put(self, chunk: str, key: str = "", origin: str = "literal") -> "Writer":
        if self._done:
            raise WriterError("writer already finished; a message is assembled once")
        if key:
            if key in self._spans:
                raise WriterError(f"chunk key {key!r} used twice in one message")
            if not chunk:
                raise WriterError(f"chunk key {key!r} carries an empty value")
            self._spans[key] = (self._length, self._length + len(chunk))
        if chunk:
            self._trace.append(TraceRow(key, self._length, self._length + len(chunk), origin))
        self._pieces.append(chunk)
        self._length += len(chunk)
        return self

    def space(self) -> "Writer":
        """A single separator, only when something precedes it."""
        if self._pieces and self._pieces[-1] and not self._pieces[-1].endswith((" ", "\n")):
            return self.put(" ")
        return self

    def words(self, *items: object) -> "Writer":
        """Space-join bare strings and (text, key) or (text, key, origin) tuples,
        dropping empties so an optional slot costs no space accounting."""
        for item in items:
            if isinstance(item, str):
                if not item:
                    continue
                self.space().put(item)
            else:
                text, key, *rest = item  # type: ignore[misc]
                if not text:
                    continue
                self.space().put(text, key, rest[0] if rest else f"value:{key}")
        return self

    def finish(self) -> tuple[str, dict[str, tuple[int, int]], tuple[TraceRow, ...]]:
        self._done = True
        text = "".join(self._pieces)
        for key, (start, end) in self._spans.items():
            if len(text[start:end]) != end - start:
                raise WriterError(f"span {key!r} does not index the text it was laid in")
        return text, dict(self._spans), tuple(self._trace)


# --- JSON emitted with the offsets known ------------------------------------

@dataclass(frozen=True)
class Slot:
    text: str
    tag: str


def _escape_free(text: str) -> str:
    for character in text:
        if character in '"\\' or unicodedata.category(character) == "Cc":
            raise WriterError(
                f"{text!r} needs JSON escaping, and an escaped value no longer "
                f"equals its span; tool-result values stay free of quotes, "
                f"backslashes and control characters")
    return text


def _emit(node: object, indent: int, level: int) -> tuple[str, dict[str, tuple[int, int]]]:
    if isinstance(node, Slot):
        body = _escape_free(node.text)
        return f'"{body}"', {node.tag: (1, 1 + len(body))}
    if isinstance(node, bool):
        return ("true" if node else "false"), {}
    if isinstance(node, str):
        return f'"{_escape_free(node)}"', {}
    if isinstance(node, int):
        return str(node), {}
    if node is None:
        return "null", {}
    if isinstance(node, dict):
        node = ("obj", tuple(node.items()))
    elif isinstance(node, list):
        node = ("arr", tuple(node))
    if not isinstance(node, tuple) or len(node) != 2:
        raise WriterError(f"cannot emit {node!r}")
    kind, children = node
    pad = ("\n" + " " * (indent * (level + 1))) if indent else ""
    close = ("\n" + " " * (indent * level)) if indent else ""
    separator = "," + (pad if indent else " ")
    spans: dict[str, tuple[int, int]] = {}
    pieces: list[str] = []
    position = 1 + len(pad)
    if kind == "obj":
        for index, (key, value) in enumerate(children):
            if index:
                pieces.append(separator)
                position += len(separator)
            head = f'"{_escape_free(str(key))}": '
            pieces.append(head)
            position += len(head)
            body, inner = _emit(value, indent, level + 1)
            for tag, (start, end) in inner.items():
                if tag in spans:
                    raise WriterError(f"tag {tag!r} written twice")
                spans[tag] = (position + start, position + end)
            pieces.append(body)
            position += len(body)
        return "{" + pad + "".join(pieces) + close + "}", spans
    if kind == "arr":
        for index, value in enumerate(children):
            if index:
                pieces.append(separator)
                position += len(separator)
            body, inner = _emit(value, indent, level + 1)
            for tag, (start, end) in inner.items():
                if tag in spans:
                    raise WriterError(f"tag {tag!r} written twice")
                spans[tag] = (position + start, position + end)
            pieces.append(body)
            position += len(body)
        return "[" + pad + "".join(pieces) + close + "]", spans
    raise WriterError(f"unknown node kind {kind!r}")


def serialise(node: object, indent: int = 2) -> tuple[str, dict[str, tuple[int, int]]]:
    """JSON text plus the span of every `Slot`. Parsed back as a build-time
    assertion: a tool result the harness cannot parse is not a tool result."""
    text, spans = _emit(node, indent, 0)
    json.loads(text)
    for tag, (start, end) in spans.items():
        if json.loads('"' + text[start:end] + '"') != text[start:end]:
            raise WriterError(f"slot {tag!r} does not round-trip as a JSON string")
    return text, spans


def main() -> int:
    failures = 0
    writer = Writer()
    writer.words("здравствуйте", ("громова марина", "n1"), "телефон",
                 ("восемь девятьсот", "p1")).put(".")
    text, spans, trace = writer.finish()
    if text != "здравствуйте громова марина телефон восемь девятьсот.":
        failures += 1
        print(f"FAIL text {text!r}")
    for key, (start, end) in spans.items():
        expected = {"n1": "громова марина", "p1": "восемь девятьсот"}[key]
        if text[start:end] != expected:
            failures += 1
            print(f"FAIL span {key} -> {text[start:end]!r}")
    try:
        writer.put("x")
        failures += 1
        print("FAIL writer accepted a chunk after finish")
    except WriterError:
        pass
    body, json_spans = serialise({"client": {"name": Slot("Громова Марина", "n"),
                                             "phones": [Slot("+79164021187", "p")]},
                                  "ok": True, "n": 3})
    for tag, (start, end) in json_spans.items():
        if body[start:end] not in ("Громова Марина", "+79164021187"):
            failures += 1
            print(f"FAIL json span {tag} -> {body[start:end]!r}")
    if json.loads(body)["client"]["phones"][0] != "+79164021187":
        failures += 1
    print("writer: PASS" if not failures else f"writer: FAIL ({failures})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
