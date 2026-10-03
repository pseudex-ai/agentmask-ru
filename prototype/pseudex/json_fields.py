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
