"""LLM Guard's `Anonymize` / `Deanonymize` scanners with their own Vault.

Unlike the Presidio adapter, nothing is added here: LLM Guard ships both
halves of the round trip and a `Vault` to hold the map, so this measures
the library as an integrator would use it.

    pip install "agentmask-ru[llm_guard]"

Two things a reader should know before reading the numbers. The scanners
are built on Presidio's English pipeline, so Russian detection is whatever
the default recognisers manage; and `use_faker=True` mints a NEW fake per
call, so the run is made with the default placeholder mode.
"""

from dataclasses import dataclass, field

from agentmask_ru.adapters.base import MaskedView, TwoPhaseSession


@dataclass
class LLMGuardSession(TwoPhaseSession):
    vault: object
    anonymize: object
    deanonymize: object

    def mask(self, messages: list[dict[str, object]], tools: list[dict[str, object]]) -> MaskedView:
        masked: list[dict[str, object]] = []
        for message in messages:
            copy = dict(message)
            content = copy.get("content")
            if isinstance(content, str):
                sanitized, _valid, _score = self.anonymize.scan(content)  # type: ignore[attr-defined]
                copy["content"] = sanitized
            masked.append(copy)
        return MaskedView(messages=masked, tools=[dict(t) for t in tools])

    def restore_arguments(self, arguments: str) -> str:
        restored, _valid, _score = self.deanonymize.scan("", arguments)  # type: ignore[attr-defined]
        return str(restored)


class LLMGuardMasker:
    name = "llm_guard"

    def __init__(self) -> None:
        import llm_guard

        self.config: dict[str, object] = {
            "adapter": "llm_guard",
            "llm_guard": getattr(llm_guard, "__version__", "unknown"),
            "mode": "default placeholders (use_faker off: a fresh fake per call breaks consistency by design)",
        }

    def open(self, case_id: str) -> LLMGuardSession:
        from llm_guard.input_scanners import Anonymize
        from llm_guard.output_scanners import Deanonymize
        from llm_guard.vault import Vault

        vault = Vault()
        return LLMGuardSession(vault=vault, anonymize=Anonymize(vault), deanonymize=Deanonymize(vault))
