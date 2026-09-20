"""LLM Guard's `Anonymize` / `Deanonymize` scanners with their own Vault.

Unlike the Presidio adapter, nothing is added here: LLM Guard ships both
halves of the round trip and a `Vault` to hold the map, so this measures
the library as an integrator would use it.

    pip install "agentmask-ru[llm_guard]"

ЧИТАТЬ ЧИСЛА ТОЛЬКО ВМЕСТЕ С ЭТИМ. LLM Guard 0.3.16 принимает ровно два
языка — `en` и `zh`; попытка передать `ru` поднимает
`LLMGuardValidationError: Language must be in the list of allowed:
['en', 'zh']`. То есть русский не поддерживается продуктом, и низкая
цифра здесь — не «плохо ищет по-русски», а «по-русски не работает вовсе».
Прогон делается на английском конвейере, потому что другого нет, и этот
факт записан в манифест прогона.

Второе: `use_faker=True` чеканит НОВУЮ подделку на каждый вызов, что ломает
консистентность по построению, поэтому прогон идёт в режиме плейсхолдеров
по умолчанию.
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

        from importlib import metadata

        try:
            version = metadata.version("llm-guard")
        except metadata.PackageNotFoundError:
            version = "unknown"
        self.config: dict[str, object] = {
            "adapter": "llm_guard",
            "llm_guard": version,
            "supported_languages": ["en", "zh"],
            "language_used": "en",
            "caveat": ("русский язык продуктом не поддерживается: Anonymize принимает только en и zh, "
                       "поэтому прогон сделан на английском конвейере"),
            "mode": "плейсхолдеры по умолчанию (use_faker выключен: новая подделка на вызов ломает консистентность)",
        }

    def open(self, case_id: str) -> LLMGuardSession:
        from llm_guard.input_scanners import Anonymize
        from llm_guard.output_scanners import Deanonymize
        from llm_guard.vault import Vault

        vault = Vault()
        return LLMGuardSession(vault=vault, anonymize=Anonymize(vault), deanonymize=Deanonymize(vault))
