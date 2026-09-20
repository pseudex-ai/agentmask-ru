"""Microsoft Presidio, made reversible the way integrators make it.

Presidio itself is a DETECTOR plus an anonymiser; `DeanonymizeEngine`
restores only what the `encrypt` operator produced, and it needs the
positions the anonymiser recorded — so it cannot restore a value the model
rewrote, and it is not what people put in front of an agent. What they put
there is this: detect, replace each entity with `<TYPE_N>`, keep the map,
and substitute back. `langchain_experimental`'s `PresidioReversibleAnonymizer`
is the same construction.

The adapter therefore measures Presidio's DETECTION with a reversible layer
we wrote — and says so. It is installed only with the `presidio` extra and
never runs in CI: the Russian spaCy model is close to a gigabyte.

    pip install "agentmask-ru[presidio]"
    python -m spacy download ru_core_news_lg
"""

from dataclasses import dataclass, field

from agentmask_ru.adapters.base import MaskedView, Span, TwoPhaseSession

# Presidio's entity names on the left, this benchmark's on the right. An
# entity Presidio finds but the benchmark does not type is still counted as
# a mask — the leak line is type-blind — but it cannot win the typed line.
_TYPES: dict[str, str] = {
    "PERSON": "NAME",
    "PHONE_NUMBER": "PHONE",
    "EMAIL_ADDRESS": "EMAIL",
    "LOCATION": "ADDRESS",
    "CREDIT_CARD": "CARD",
    "DATE_TIME": "DOB",
    "IBAN_CODE": "CARD",
}


def _analyzer(language: str):
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider

    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": language, "model_name": "ru_core_news_lg" if language == "ru" else "en_core_web_lg"}],
    })
    return AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=[language])


@dataclass
class PresidioSession(TwoPhaseSession):
    analyzer: object
    language: str
    to_placeholder: dict[str, str] = field(default_factory=dict)
    to_value: dict[str, str] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)

    def _placeholder(self, kind: str, value: str) -> str:
        if value in self.to_placeholder:
            return self.to_placeholder[value]
        self.counters[kind] = self.counters.get(kind, 0) + 1
        token = f"<{kind}_{self.counters[kind]}>"
        self.to_placeholder[value] = token
        self.to_value[token] = value
        return token

    def _mask_text(self, text: str) -> str:
        results = self.analyzer.analyze(text=text, language=self.language)  # type: ignore[attr-defined]
        # Right to left, so an earlier replacement does not move the offsets
        # of a later one.
        out = text
        for result in sorted(results, key=lambda r: -r.start):
            value = text[result.start:result.end]
            out = out[:result.start] + self._placeholder(str(result.entity_type), value) + out[result.end:]
        return out

    def mask(self, messages: list[dict[str, object]], tools: list[dict[str, object]]) -> MaskedView:
        masked: list[dict[str, object]] = []
        for message in messages:
            copy = dict(message)
            content = copy.get("content")
            if isinstance(content, str):
                copy["content"] = self._mask_text(content)
            masked.append(copy)
        return MaskedView(messages=masked, tools=[dict(t) for t in tools])

    def restore_arguments(self, arguments: str) -> str:
        out = arguments
        for token, value in self.to_value.items():
            out = out.replace(token, value)
        return out

    def spans(self, text: str) -> list[Span]:
        results = self.analyzer.analyze(text=text, language=self.language)  # type: ignore[attr-defined]
        return [
            Span(start=r.start, end=r.end, type=_TYPES.get(str(r.entity_type), str(r.entity_type)))
            for r in sorted(results, key=lambda r: r.start)
        ]


class PresidioMasker:
    name = "presidio"

    def __init__(self, language: str) -> None:
        self._language = language
        self._analyzer = _analyzer(language)
        from importlib import metadata

        def _version(name: str) -> str:
            try:
                return metadata.version(name)
            except metadata.PackageNotFoundError:
                return "not installed"

        self.config: dict[str, object] = {
            "adapter": "presidio",
            "language": language,
            "presidio_analyzer": _version("presidio-analyzer"),
            "presidio_anonymizer": _version("presidio-anonymizer"),
            "spacy_model": "ru_core_news_lg" if language == "ru" else "en_core_web_lg",
            "recognizers": "по умолчанию, без настройки под РФ",
            "reversibility": "карта плейсхолдеров ведётся адаптером, обратная подстановка точная",
        }

    def open(self, case_id: str) -> PresidioSession:
        return PresidioSession(analyzer=self._analyzer, language=self._language)
