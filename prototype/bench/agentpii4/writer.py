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


def _escape(text: str) -> str:
    """The content of one JSON string literal for `text`.

    Every character JSON must escape — `"`, `\\`, newline and the rest of the
    controls — is written as its escape; everything else, Cyrillic included,
    stays raw. `ensure_ascii=False` is load-bearing: `True` would rewrite every
    name in the corpus as `\\uXXXX`, and the span laid down beside it would no
    longer equal it.

    `json.dumps` is the escaper rather than a hand-rolled table because a second
    spelling of «what JSON escapes» would drift from the parser the moment one of
    the two changes. The old `_escape_free` REFUSED these values, which is what
    turned a model's multi-line summary into an excluded triple rather than a
    valid result.
    """
    return json.dumps(text, ensure_ascii=False)[1:-1]


def _emit(node: object, indent: int, level: int) -> tuple[str, dict[str, tuple[int, int]]]:
    if isinstance(node, Slot):
        escaped = _escape(node.text)
        return f'"{escaped}"', {node.tag: (1, 1 + len(escaped))}
    if isinstance(node, bool):
        return ("true" if node else "false"), {}
    if isinstance(node, str):
        return f'"{_escape(node)}"', {}
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
            head = f'"{_escape(str(key))}": '
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
        content = text[start:end]
        # The span covers the ESCAPED bytes; round-trip it through the parser and
        # the escaper, so a span that points one byte short or long of the literal
        # is refused rather than masked wrong. An escaped value (two bytes for one
        # newline) is accounted here, which is what the old byte-equality check
        # could not express.
        if _escape(json.loads('"' + content + '"')) != content:
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
    failures += _multiline_check()
    print("writer: PASS" if not failures else f"writer: FAIL ({failures})")
    return 1 if failures else 0


def _multiline_check() -> int:
    """A multi-line value is EMITTED as escaped JSON, not refused: the span
    covers the escaped bytes and round-trips back to the source text."""
    failures = 0
    value = "перенос\nвторой абзац \"цитата\" и \\ слэш"
    body, spans = serialise({"text": Slot(value, "m")})
    if json.loads(body)["text"] != value:
        failures += 1
        print(f"FAIL multiline value did not round-trip: {body!r}")
    start, end = spans["m"]
    if json.loads('"' + body[start:end] + '"') != value:
        failures += 1
        print(f"FAIL multiline span does not round-trip to the source: "
              f"{body[start:end]!r}")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
