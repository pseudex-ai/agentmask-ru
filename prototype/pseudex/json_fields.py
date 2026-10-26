"""Source-offset JSON string leaves and their structural ownership paths.

This module does not decide what is PII. It only prevents lexical evidence in
one JSON value from being attributed to another. Decoded values never replace
source offsets: all spans refer to the exact serialized text the caller sent.
Invalid/non-JSON text has no structural evidence and uses the prose path.
"""
import json
import re
from typing import NamedTuple


class StringLeaf(NamedTuple):
    start: int
    end: int
    path: tuple[str | int, ...]


_TOKEN = re.compile(
    r'"(?:[^"\\]|\\.)*"|[{}\[\]:,]|true|false|null|'
    r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?', re.DOTALL)


def string_leaves(text: str) -> tuple[StringLeaf, ...]:
    """All STRING VALUES, never object keys, of a valid object/array payload.

    A surrounding object key remains in the path for array values as well, so
    `{"birth_dates": ["..."]}` can be distinguished by policy from a slots
    array. Returning nothing on malformed JSON does not suppress detection;
    the ordinary lexical recognizers still inspect that input.
    """
    if not text.lstrip().startswith(('{', '[')):
        return ()
    try:
        root = json.loads(text)
    except (ValueError, RecursionError):
        return ()
    if not isinstance(root, (dict, list)):
        return ()
    tokens = list(_TOKEN.finditer(text))
    leaves: list[StringLeaf] = []
    index = 0

    def value(path: tuple[str | int, ...]) -> None:
        nonlocal index
        token = tokens[index]
        literal = token.group()
        index += 1
        if literal == '{':
            if tokens[index].group() == '}':
                index += 1
                return
            while True:
                key = json.loads(tokens[index].group())
                index += 2  # key plus colon; syntax already validated above
                value((*path, key))
                delimiter = tokens[index].group()
                index += 1
                if delimiter == '}':
                    return
        elif literal == '[':
            if tokens[index].group() == ']':
                index += 1
                return
            item = 0
            while True:
                value((*path, item))
                item += 1
                delimiter = tokens[index].group()
                index += 1
                if delimiter == ']':
                    return
        elif literal.startswith('"'):
            leaves.append(StringLeaf(token.start() + 1, token.end() - 1, path))

    try:
        value(())
    except (IndexError, ValueError, RecursionError):
        # Never offer a partial structure as authoritative evidence. Detection
        # falls back to prose for the whole input if structure cannot be read.
        return ()
    return tuple(leaves) if index == len(tokens) else ()


def scalar_map(text: str) -> tuple[dict[tuple[str | int, ...], tuple[int, int]], str]:
    """Full scalar lexemes (including string quotes), indexed structurally.

    Unlike string_leaves this accepts root scalars and numbers. No decoded-to-
    lexical interpolation: a changed leaf owns its WHOLE lexeme. Duplicate keys
    make JSON Pointers ambiguous, including duplicate container keys whose child
    names differ, so no partial authoritative map is returned in that case.
    """
    decoder = json.JSONDecoder()
    leaves: dict[tuple[str | int, ...], tuple[int, int]] = {}
    duplicate = False
    at = 0

    def whitespace() -> None:
        nonlocal at
        while at < len(text) and text[at] in " \t\r\n":
            at += 1

    def value(path: tuple[str | int, ...]) -> None:
        nonlocal at, duplicate
        whitespace()
        start = at
        if text[at] == "{":
            at += 1
            whitespace()
            seen = set()
            if text[at] == "}":
                at += 1
                return
            while True:
                key, at = decoder.raw_decode(text, at)
                if not isinstance(key, str):
                    raise ValueError("non-string object key")
                duplicate = duplicate or key in seen
                seen.add(key)
                whitespace()
                if text[at] != ":":
                    raise ValueError("missing colon")
                at += 1
                value((*path, key))
                whitespace()
                delimiter = text[at]
                at += 1
                if delimiter == "}":
                    return
                if delimiter != ",":
                    raise ValueError("missing comma")
                whitespace()
        elif text[at] == "[":
            at += 1
            whitespace()
            if text[at] == "]":
                at += 1
                return
            index = 0
            while True:
                value((*path, index))
                index += 1
                whitespace()
                delimiter = text[at]
                at += 1
                if delimiter == "]":
                    return
                if delimiter != ",":
                    raise ValueError("missing comma")
        else:
            _decoded, at = decoder.raw_decode(text, at)
            leaves[path] = (start, at)

    try:
        value(())
        whitespace()
        if at != len(text):
            raise ValueError("trailing content")
    except (ValueError, IndexError, TypeError, RecursionError):
        return {}, "json_lexical_map_unavailable"
    return ({}, "duplicate_json_keys") if duplicate else (leaves, "")
