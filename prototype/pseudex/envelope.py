"""Transformations over the OpenAI chat wire envelope — the part both deployment
shapes share.

`proxy.py` (we call the provider) and `service.py` (a host gateway calls us) each
carried their own copy of this traversal and DRIFTED: multi-part content blocks,
the mask cache and the template skip existed only in the sidecar, so the proxy leg
silently masked less than the sidecar did. Owning the traversal here means a newly
handled message field lands on both legs at once, or on neither — never on one.

The envelope is walked, not the transport: nothing here knows whether the caller
forwards the request itself or hands it back to a host gateway.
"""

import hashlib
from dataclasses import dataclass

from pseudex.audit import AuditLog
from pseudex.detect_all import Detector
from pseudex.maskcache import MaskCache, content_key
from pseudex.profiling import stage
from pseudex.redact import (is_own_substitute, mask_text, tokenize_span, unmask_arguments,
                            unmask_text)
from pseudex.vault import Vault


@dataclass(frozen=True)
class MaskContext:
    """Everything one masking pass needs. Grouped so the traversal functions stay
    readable and a new dependency doesn't ripple through every signature."""

    detector: Detector
    vault: Vault
    audit: AuditLog
    cache: MaskCache
    org_id: str
    agent_id: str
    # The conversation this pass belongs to, empty when the caller names none.
    # Part of the cache key and the vault view — see `content_key` and
    # `Vault.for_conversation` for why a link decided here must not escape it.
    conversation_id: str



def conversation_key(messages: list[dict[str, object]]) -> str:
    """A conversation identity derived from the transcript itself.

    The caller may name the conversation and should; but neither wire format has
    a field for it — OpenAI's chat API has no conversation id, and a host gateway
    that never needed one will not start sending it because we added a scope. So
    the id is derived when it is not given, and the transcript supplies it: the
    OPENING messages of a conversation do not change as it grows, which is
    exactly the stability an identity needs.

    The first two messages, not one: a system prompt is often shared by every
    conversation an agent has, so hashing it alone would put the whole tenant in
    one scope and defeat the point. The first user turn is what differs.

    Hashed, never stored raw — this runs on customer text and the value is
    carried in cache keys and log-adjacent places where PII must not appear.

    A derived id is WEAKER than a given one and knowingly so: two conversations
    opening with byte-identical messages share a scope. The failure that causes
    is a partial mention resolving against the other conversation's address, so
    the linking rule must stay single-candidate — with two addresses in scope it
    refuses, which is the safe answer.
    """
    digest = hashlib.sha256()
    for message in messages[:2]:
        content = message.get("content")
        if isinstance(content, str):
            digest.update(content.encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()[:32]

def mask_one(text: str, context: MaskContext) -> str:
    """Mask one text. A content-keyed cache makes re-masking the SAME raw text
    (the O(n^2) growing-transcript case) an O(1) hit; the audit is recorded only
    on the cache MISS, so a value is counted once per unique (org, content), not
    once per resend.

    EVERY text goes through full detection — there is NO pre-filter skip. A
    pre-filter would have to stay a perfect superset of every recognizer's
    triggers forever; it silently failed that invariant (single Latin names and
    Latin-keyed KV like {"name":"john"} leaked raw to the model). In a fail-closed
    PII gateway that risk is unacceptable, and the cache already removes the
    repeated-work cost, so detection is never skipped."""
    def _compute() -> str:
        # Spans whose value is one of OUR OWN tokens are dropped BEFORE anything
        # is minted or recorded. `mask_text` already refuses to replace them, but
        # this loop ran first and did not: an echoed token got a vault row of its
        # own (fake -> another fake, burning a slot in a finite pool) and an audit
        # event, which is the number the licensing server bills on. In a
        # multi-turn agent the model quotes its own tokens constantly, so the
        # inflation was proportional to conversation length.
        spans = [span for span in context.detector.detect(text)
                 if not is_own_substitute(span, context.vault)]
        with stage("mask.tokenize_and_audit"):
            # Collected first, written once: one commit per MESSAGE instead of one
            # per entity. See AuditLog.record_many — per-span commits made four
            # workers under load fail most requests with `database is locked`.
            events = [
                (span.entity_type, tokenize_span(span, context.vault), span.value)
                for span in spans
            ]
            context.audit.record_many(context.org_id, context.agent_id, events)
        with stage("mask.splice"):
            return mask_text(text, context.vault, spans)

    with stage("mask.one"):
        masked, _hit = context.cache.get_or_compute(
            content_key(context.org_id, context.conversation_id, text), _compute
        )
    return masked


def _mask_content(content: object, context: MaskContext) -> object:
    """Mask a message's `content`, which is either a plain string or a list of
    content blocks (vision / multi-part). Non-text blocks (image_url,
    input_audio, …) pass through untouched; without the list branch, PII sitting
    in a text block of a multi-part message would reach the provider unmasked."""
    if isinstance(content, str):
        return mask_one(content, context)
    if not isinstance(content, list):
        return content
    blocks: list[object] = []
    for block in content:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            masked_block = dict(block)
            masked_block["text"] = mask_one(block["text"], context)
            blocks.append(masked_block)
        else:
            blocks.append(block)
    return blocks


def _mask_tool_calls(tool_calls: object, context: MaskContext) -> object:
    """Mask the arguments of assistant tool calls replayed in the transcript."""
    if not isinstance(tool_calls, list):
        return tool_calls
    masked: list[object] = []
    for call in tool_calls:
        if not isinstance(call, dict):
            masked.append(call)
            continue
        new_call = dict(call)
        function = new_call.get("function")
        if isinstance(function, dict):
            new_function = dict(function)
            if isinstance(new_function.get("arguments"), str):
                new_function["arguments"] = mask_one(new_function["arguments"], context)
            new_call["function"] = new_function
        masked.append(new_call)
    return masked


def mask_messages(
    messages: list[dict[str, object]],
    context: MaskContext,
    skip_template: bool,
) -> list[dict[str, object]]:
    """Mask every message. `skip_template` is OPT-IN and set only by the engine
    leg: there the system prompt is the agent's own template, not user PII, and
    running NER over tens of KB on every call is the bulk of the cost and could
    corrupt instructions. The PUBLIC /v1 leg does NOT skip — there the customer
    writes the system message and may put PII in it, which MUST be masked or it
    reaches the provider raw and breaks the Protected-key promise."""
    masked: list[dict[str, object]] = []
    for message in messages:
        new_message = dict(message)
        if skip_template and message.get("role") == "system":
            masked.append(new_message)
            continue
        # Only touch `content` if the message HAD one. Assigning unconditionally
        # added `"content": null` to assistant turns that carry only `tool_calls`
        # — a message shape neither leg produced before. Strict providers reject
        # the extra null field, and it also perturbs the byte-identical prefix
        # that prefix-cache accounting depends on.
        if "content" in new_message:
            new_message["content"] = _mask_content(new_message["content"], context)
        if "tool_calls" in new_message:
            new_message["tool_calls"] = _mask_tool_calls(
                new_message["tool_calls"], context
            )
        masked.append(new_message)
    return masked


# Ключи схемы, под которыми лежит ВЛОЖЕННАЯ схема, а не значение. Обход идёт по
# ним, а не «по всем словарям подряд»: `enum` и `default` тоже словари или
# списки, и заходить в них нельзя — это КОНТРАКТ, а не текст.
_SCHEMA_BRANCHES: tuple[str, ...] = ("properties", "$defs", "definitions", "patternProperties")
_SCHEMA_NODES: tuple[str, ...] = ("items", "additionalProperties", "contains", "not")
_SCHEMA_LISTS: tuple[str, ...] = ("anyOf", "oneOf", "allOf", "prefixItems")
# Три формы описания инструмента, которые встречаются в поле. OpenAI кладёт
# схему под `function.parameters`, MCP — под `inputSchema`, Anthropic — под
# `input_schema`.
_SCHEMA_KEYS: tuple[str, ...] = ("parameters", "inputSchema", "input_schema")


def _mask_schema(node: object, context: MaskContext) -> object:
    """Схема JSON, у которой замаскированы все `description`, НА ЛЮБОЙ ГЛУБИНЕ.

    ОБХОД БЫЛ РОВНО ДВА УРОВНЯ, и этого мало для настоящей схемы. Пример с
    телефоном внутри `recipient.phones[].number.description` уходил провайдеру
    сырым на КАЖДОМ вызове — вложенный объект, элемент массива, ветка `anyOf`,
    цель `$ref` из `$defs`: ни одного из них старый обход не видел. Персональные
    данные в описании — это то, что писал разработчик заказчика, а не модель, и
    попадают они туда именно в примерах вложенных полей.

    `enum`, `const` и `default` НЕ ТРОГАЮТСЯ и не обходятся: это множество
    значений, которые модели РАЗРЕШЕНО писать, то есть контракт. Подменить их
    значит изменить контракт — обоснование то же, что было у прежней версии, и
    оно не изменилось от того, что обход стал глубже.
    """
    if isinstance(node, list):
        return [_mask_schema(one, context) for one in node]
    if not isinstance(node, dict):
        return node
    out = dict(node)
    if isinstance(out.get("description"), str):
        out["description"] = mask_one(out["description"], context)
    if isinstance(out.get("title"), str):
        out["title"] = mask_one(out["title"], context)
    for key in _SCHEMA_BRANCHES:
        if isinstance(out.get(key), dict):
            out[key] = {name: _mask_schema(one, context) for name, one in out[key].items()}
    for key in _SCHEMA_NODES:
        if isinstance(out.get(key), (dict, list)):
            out[key] = _mask_schema(out[key], context)
    for key in _SCHEMA_LISTS:
        if isinstance(out.get(key), list):
            out[key] = [_mask_schema(one, context) for one in out[key]]
    return out


def mask_tools(
    tools: object,
    context: MaskContext,
    skip_template: bool,
) -> object:
    """Mask the free-text DESCRIPTIONS of tool schemas.

    Tool descriptions routinely carry worked examples ("найти заказ, например
    phone='+79991234567'") and that phone reaches the provider on every single
    call. Because tokens are format-preserving the example stays a well-formed
    phone, so the model loses nothing.

    Only `description` (and `title`) fields are touched. Names, types and `enum`
    values are the tool CONTRACT: masking an enum would change the set of values
    the model is allowed to emit, and masking a name would break dispatch.

    ТРИ ФОРМЫ, А НЕ ОДНА. Прежняя версия требовала ключ `function` и молча
    пропускала инструмент без него — а это ровно форма MCP (`inputSchema`) и
    форма Anthropic (`input_schema`), у которых описание и схема лежат на
    верхнем уровне. Инструмент такой формы уходил провайдеру НЕТРОНУТЫМ
    целиком.

    `skip_template` follows the same rule as the system prompt — on the engine leg
    the schemas are the agent's own template and are left alone."""
    if skip_template or not isinstance(tools, list):
        return tools
    masked: list[object] = []
    for tool in tools:
        if not isinstance(tool, dict):
            masked.append(tool)
            continue
        new_tool = dict(tool)
        if isinstance(new_tool.get("function"), dict):
            new_tool["function"] = _mask_tool_body(new_tool["function"], context)
        else:
            new_tool = _mask_tool_body(new_tool, context)
        masked.append(new_tool)
    return masked


def _mask_tool_body(body: dict[str, object], context: MaskContext) -> dict[str, object]:
    """Описание инструмента и его схема, в какой бы из трёх форм они ни лежали."""
    out = dict(body)
    if isinstance(out.get("description"), str):
        out["description"] = mask_one(out["description"], context)
    for key in _SCHEMA_KEYS:
        if isinstance(out.get(key), dict):
            out[key] = _mask_schema(out[key], context)
    return out


def unmask_response(response: dict[str, object], vault: Vault) -> dict[str, object]:
    """Detokenize a non-streamed completion: assistant content + tool-call
    arguments. Rebuilt rather than mutated so the caller's object is untouched."""
    result = dict(response)
    choices = result.get("choices")
    if not isinstance(choices, list):
        return result
    new_choices: list[object] = []
    for choice in choices:
        if not isinstance(choice, dict):
            new_choices.append(choice)
            continue
        new_choice = dict(choice)
        message = new_choice.get("message")
        if isinstance(message, dict):
            new_message = dict(message)
            if isinstance(new_message.get("content"), str):
                new_message["content"] = unmask_text(new_message["content"], vault)
            tool_calls = new_message.get("tool_calls")
            if isinstance(tool_calls, list):
                restored: list[object] = []
                for call in tool_calls:
                    if not isinstance(call, dict):
                        restored.append(call)
                        continue
                    new_call = dict(call)
                    function = new_call.get("function")
                    if isinstance(function, dict):
                        new_function = dict(function)
                        if isinstance(new_function.get("arguments"), str):
                            new_function["arguments"] = unmask_arguments(
                                new_function["arguments"], vault
                            )
                        new_call["function"] = new_function
                    restored.append(new_call)
                new_message["tool_calls"] = restored
            new_choice["message"] = new_message
        new_choices.append(new_choice)
    result["choices"] = new_choices
    return result
