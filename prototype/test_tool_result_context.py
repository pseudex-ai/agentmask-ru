"""Standard transcript call/result association, without model calls or vault state."""

import copy
import json

from pseudex.envelope import tool_result_contexts


def call(call_id: str, name: str, value: str) -> dict[str, object]:
    return {"id": call_id, "type": "function", "function": {
        "name": name, "arguments": json.dumps({"phone": value})}}


def main() -> int:
    first: dict[str, object] = call("a", "lookup", "first")
    second: dict[str, object] = call("b", "lookup", "second")
    assistant: dict[str, object] = {"role": "assistant", "tool_calls": [first, second]}
    result_a: dict[str, object] = {"role": "tool", "tool_call_id": "a", "content": "error"}
    result_b: dict[str, object] = {"role": "tool", "tool_call_id": "b", "content": "error"}
    rows: list[tuple[str, list[dict[str, object]], list[tuple[str, str]]]] = [
        ("parallel same-name reversed results", [assistant, result_b, result_a],
         [("not_result", ""), ("matched", "second"), ("matched", "first")]),
        ("no future evidence", [result_a, assistant, result_a],
         [("missing", ""), ("not_result", ""), ("matched", "first")]),
        ("duplicate id even with identical values", [assistant, {"role": "assistant", "tool_calls": [first]}, result_a],
         [("not_result", ""), ("not_result", ""), ("ambiguous", "")]),
        ("user content cannot declare calls", [{"role": "user", "tool_calls": [first]}, result_a],
         [("not_result", ""), ("missing", "")]),
        ("wrong tool name", [assistant, {**result_a, "name": "different"}],
         [("not_result", ""), ("invalid", "")]),
        # `name` is OPTIONAL on the wire. A provider that spells its absence with
        # an explicit `null` is saying the same thing as a provider that omits the
        # key, and neither may cost the result its unique matched id.
        ("null tool name is absent, not wrong", [assistant, {**result_a, "name": None}],
         [("not_result", ""), ("matched", "first")]),
        ("missing result id", [assistant, {"role": "tool", "content": "error"}],
         [("not_result", ""), ("missing", "")]),
        ("no cross-transcript state", [result_a], [("missing", "")]),
        ("same id in separate transcript", [{"role": "assistant", "tool_calls": [call("a", "lookup", "other")]}, result_a],
         [("not_result", ""), ("matched", "other")]),
        ("malformed duplicate invalidates original", [assistant, {"role": "assistant", "tool_calls": [{"id": "a"}]}, result_a],
         [("not_result", ""), ("not_result", ""), ("ambiguous", "")]),
        ("invalid argument JSON", [{"role": "assistant", "tool_calls": [{"id": "a", "type": "function",
          "function": {"name": "lookup", "arguments": "{"}}]}, result_a],
         [("not_result", ""), ("invalid", "")]),
        ("later duplicate cannot rewrite earlier evidence", [assistant, result_a, {"role": "assistant", "tool_calls": [first]}, result_a],
         [("not_result", ""), ("matched", "first"), ("not_result", ""), ("ambiguous", "")]),
        ("result blocks stay associated", [assistant, {**result_b, "content": [{"type": "text", "text": "error"}]}],
         [("not_result", ""), ("matched", "second")]),
    ]
    failures: list[str] = []
    for label, messages, expected in rows:
        before: list[dict[str, object]] = copy.deepcopy(messages)
        contexts = tool_result_contexts(messages)
        observed: list[tuple[str, str]] = [
            (item.status, str(json.loads(item.call.arguments)["phone"]) if item.call is not None else "")
            for item in contexts]
        if observed != expected or messages != before:
            failures.append(label)
    for failure in failures:
        print("FAIL", failure)
    print(f"tool_result_context: {len(rows) - len(failures)}/{len(rows)}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
