"""What the model does with what it is shown.

The benchmark needs a model that is deterministic, free, and harsher than a
real one. `copier` is that model: it reads the masked messages, works out
what stands where each personal value used to be, and copies exactly that
into the tool call. A real model paraphrases and occasionally drops a digit;
forgiving that would hide a round-trip break, so the scripted model forgives
nothing.

`reformat` is the one model habit the benchmark does model: a phone gets its
separators stripped and its prefix swapped on the way into an argument. Every
model does this, and it is the cheapest version of the question «can the
gateway restore a substitute the model REWROTE» — the full version (case,
transliteration, initials) is out of scope for v0.1.

WHY THE POLICY LOOKS AT THE MASKED TEXT AND NOT AT THE CASE. It is handed
the substitutes the alignment found, never the gold values. A policy that
read the ground truth would produce a perfect call through any masker and
the round trip would measure nothing.
"""

import json
import random
from dataclasses import dataclass

from agentmask_ru.adapters.base import MaskedView, ModelReply, ToolCall
from agentmask_ru.align import project
from agentmask_ru.registers import reformat_phone
from agentmask_ru.schema import Case

POLICIES: tuple[str, ...] = ("copier", "reformat")


@dataclass(frozen=True)
class Seen:
    """One gold item as the model saw it."""

    item_id: str
    tool_param: str | None
    text: str
    altered: bool
    covered: bool


def observe(case: Case, masked: MaskedView, upto_turn: int) -> list[Seen]:
    """Project every gold span of the turns the model has been shown."""
    seen: list[Seen] = []
    for item in case.pii:
        if item.turn > upto_turn:
            continue
        original = case.messages[item.turn]["content"]
        shown = masked.messages[item.turn].get("content")
        if not isinstance(shown, str):
            continue
        substitute = project(original, shown, item.start, item.end)
        seen.append(Seen(
            item_id=item.id, tool_param=item.tool_param, text=substitute.text,
            altered=substitute.altered, covered=substitute.covered,
        ))
    return seen


def decide(case: Case, masked: MaskedView, upto_turn: int, policy: str, rng: random.Random) -> tuple[ModelReply, list[Seen]]:
    """The scripted model's reply for one turn.

    Until the last user turn it says «Принято.» and calls nothing; on the
    last turn it emits the expected call, filled from what it saw.
    """
    seen = observe(case, masked, upto_turn)
    last_user = max(i for i, m in enumerate(case.messages) if m["role"] == "user")
    if upto_turn < last_user:
        return ModelReply(text="Принято.", tool_call=None), seen

    arguments: dict[str, str] = {}
    by_param = {s.tool_param: s for s in seen if s.tool_param}
    for param in case.expected_call.pii_params:
        observed = by_param.get(param)
        if observed is None:
            continue
        value = observed.text
        if policy == "reformat" and param == "phone":
            value = reformat_phone(value, rng)
        arguments[param] = value
    for param, value in case.expected_call.plain_params.items():
        # Negatives travel through the model too: an order number the
        # gateway masked would arrive here as a placeholder, and the tool
        # would fail on a value that was never personal data.
        shown = masked.messages[_turn_of_plain(case, value)].get("content")
        arguments[param] = _as_shown(case, value, shown if isinstance(shown, str) else "")
    call = ToolCall(name=case.expected_call.name, arguments=json.dumps(arguments, ensure_ascii=False))
    return ModelReply(text=None, tool_call=call), seen


def _turn_of_plain(case: Case, value: str) -> int:
    for negative in case.negatives:
        if negative.value == value:
            return negative.turn
    return max(i for i, m in enumerate(case.messages) if m["role"] == "user")


def _as_shown(case: Case, value: str, shown: str) -> str:
    """A plain parameter as the model saw it: if the gateway masked the
    order number, the model copies the placeholder, and the tool receives
    whatever the gateway restores — usually the placeholder itself."""
    for negative in case.negatives:
        if negative.value != value:
            continue
        original = case.messages[negative.turn]["content"]
        substitute = project(original, shown, negative.start, negative.end)
        return substitute.text
    return value
