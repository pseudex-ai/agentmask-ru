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
from pseudex.redact import mask_text, unmask_arguments, unmask_text
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
                 if not context.vault.is_minted_token(span.value)]
        with stage("mask.tokenize_and_audit"):
            # Collected first, written once: one commit per MESSAGE instead of one
            # per entity. See AuditLog.record_many — per-span commits made four
            # workers under load fail most requests with `database is locked`.
            events = [
                (span.entity_type,
                 context.vault.tokenize(span.value, span.entity_type),
                 span.value)
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

    Only `description` fields are touched. Names, types and `enum` values are the
    tool CONTRACT: masking an enum would change the set of values the model is
    allowed to emit, and masking a name would break dispatch.

    `skip_template` follows the same rule as the system prompt — on the engine leg
    the schemas are the agent's own template and are left alone."""
    if skip_template or not isinstance(tools, list):
        return tools
    masked: list[object] = []
    for tool in tools:
        if not isinstance(tool, dict) or not isinstance(tool.get("function"), dict):
            masked.append(tool)
            continue
        new_tool = dict(tool)
        function = dict(new_tool["function"])
        if isinstance(function.get("description"), str):
            function["description"] = mask_one(function["description"], context)
        parameters = function.get("parameters")
        if isinstance(parameters, dict) and isinstance(parameters.get("properties"), dict):
            new_parameters = dict(parameters)
            properties: dict[str, object] = {}
            for name, schema in parameters["properties"].items():
                if isinstance(schema, dict) and isinstance(schema.get("description"), str):
                    new_schema = dict(schema)
                    new_schema["description"] = mask_one(schema["description"], context)
                    properties[name] = new_schema
                else:
                    properties[name] = schema
            new_parameters["properties"] = properties
            function["parameters"] = new_parameters
        new_tool["function"] = function
        masked.append(new_tool)
    return masked


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
