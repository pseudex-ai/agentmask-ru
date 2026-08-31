"""Arm B: the same masking a customer's gateway does, driven turn by turn.

THE OFFLINE SCORER MASKS THE WHOLE TRANSCRIPT AT ONCE AND THAT IS RIGHT THERE —
it holds a finished dialogue. A live run does not have one: the second user turn
is sent only after the model has answered the first, and the tool result the
model reads was produced by a call it decided to make. So the transcript GROWS,
and every request masks all of it, which is exactly the shape of a real request:
an OpenAI-compatible body carries the whole array every time.

WHAT GOES INTO THE TRANSCRIPT IS WHAT THE WIRE CARRIES, and for the assistant
turns that is the MASKED text the model wrote — not some plain original, which
does not exist. Re-masking them is safe by construction: `mask_text` leaves a
span alone when its value is already a token we issued, which is the property
that makes a growing masked transcript stable at all.

THE SYSTEM MESSAGE IS MASKED (`skip_template=False`). That is the public leg,
where the customer writes the system prompt and may put a person in it. The
engine leg skips it for cost; taking the stricter of the two here means a leak
out of a system prompt counts, and `schema.validate` refuses a gold item there
anyway so the choice cannot flatter a score.

TOOL SCHEMAS ARE MASKED TOO. `envelope.mask_tools` rewrites the free-text
descriptions, because a worked example in a description («phone='+79991234567'»)
reaches the provider on every call. It can also change what the model does, and
that is not a reason to skip it — it is the leg the product ships, and a
transparency number measured with a step of the product switched off is a number
about a different product.
"""

import json

from bench.agentpii2.schema import Case
from pseudex.audit import AuditLog
from pseudex.envelope import MaskContext, conversation_key, mask_messages, mask_tools
from pseudex.maskcache import MaskCache
from pseudex.redact import residual_tokens, unmask_arguments, unmask_text
from pseudex.vault import Vault


class LiveGateway:
    """One conversation's masking session. A class because it owns the vault
    view and the growing transcript — external state with a lifetime."""

    def __init__(self, case: Case, detector: object, vault: Vault,
                 audit: AuditLog, cache: MaskCache) -> None:
        conversation = case.conversation_id or conversation_key(case.messages)
        self._conversation = conversation
        self._base = vault
        self._view = vault.for_conversation(conversation)
        self._context = MaskContext(detector=detector, vault=self._view, audit=audit,
                                    cache=cache, org_id="bench-live",
                                    agent_id="bench-live",
                                    conversation_id=conversation)
        self._transcript: list[dict[str, object]] = []

    @property
    def conversation_id(self) -> str:
        return self._conversation

    def prime(self, lead: Case) -> None:
        """Mask an earlier conversation into the SAME tenant vault without
        calling the model.

        `preceded_by` says this case was preceded by another against one tenant,
        and the `scope` family's claim — that a partial mention here must NOT
        resolve against that one — is empty unless the lead is really in the
        vault. Running the lead through the model as well would double its cost
        and add nothing: the claim is about the vault, and the model never sees
        the lead's conversation.
        """
        lead_conversation = lead.conversation_id or conversation_key(lead.messages)
        context = MaskContext(detector=self._context.detector,
                              vault=self._base.for_conversation(lead_conversation),
                              audit=self._context.audit, cache=self._context.cache,
                              org_id=self._context.org_id,
                              agent_id=self._context.agent_id,
                              conversation_id=lead_conversation)
        mask_messages([dict(message) for message in lead.messages], context, False)

    def tools(self, schemas: list[dict[str, object]]) -> list[dict[str, object]]:
        masked = mask_tools([dict(schema) for schema in schemas], self._context, False)
        if not isinstance(masked, list):
            raise TypeError("mask_tools вернул не список — форма контракта изменилась")
        return [schema for schema in masked if isinstance(schema, dict)]

    def push(self, message: dict[str, object]) -> str:
        """Append one message and return what the model reads in its place.

        The WHOLE transcript is re-masked, not just the new message: the
        substitute a later mention gets depends on what earlier ones put in the
        vault, and masking message by message would be a different product.
        """
        self._transcript.append(dict(message))
        masked = mask_messages([dict(one) for one in self._transcript],
                               self._context, False)
        content = masked[-1].get("content")
        return content if isinstance(content, str) else ""

    def note(self, message: dict[str, object]) -> None:
        """Record a turn the model itself produced. Already masked — it was
        written from masked input — so it is appended, not re-derived."""
        self._transcript.append(dict(message))

    def restore(self, arguments: dict[str, object]) -> tuple[dict[str, object], list[str]]:
        """Detokenise a tool call the way the sidecar does, and report residuals.

        `unmask_arguments`, never a flat replace: an argument object is JSON and
        a real value is arbitrary text, so «ООО "Заря"» spliced in by string
        substitution injects two bare quotes and the call stops parsing. The
        residual list is the other half — a substitute that resolved to nothing
        leaves well-formed JSON and a 200, and the caller has no other way to
        find out that a fake reached the tool.
        """
        restored = unmask_arguments(json.dumps(arguments, ensure_ascii=False),
                                    self._base)
        try:
            parsed = json.loads(restored)
        except json.JSONDecodeError:
            return {}, ["<детокенизация сломала собственный JSON>"]
        if not isinstance(parsed, dict):
            return {}, ["<детокенизация вернула не объект>"]
        residual: list[str] = []
        for value in parsed.values():
            if isinstance(value, str):
                residual.extend(residual_tokens(value, self._base))
        return parsed, residual

    def restore_text(self, text: str) -> str:
        """The assistant's prose on the way back to the customer. A different
        endpoint from the one above and deliberately so: flat text is what
        `/unmask` handles, and routing a tool argument through it is the defect
        `unmask_arguments` exists to prevent."""
        return unmask_text(text, self._base)
