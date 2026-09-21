"""The two reference maskers. Neither is a product; both exist so every
number on the leaderboard has a floor and a ceiling to sit between, and so
the corpus itself can be checked (gates G6 and G7).

`noop` changes nothing. It must score zero on every protection line and a
perfect score on over-masking and on the end-to-end line — if it does not,
the CASE is wrong, not the masker: a canonical value that a passthrough
cannot deliver is a canonical value nobody can deliver.

`placeholder_regex` is the naive thing everybody writes first: regexes for
the shapes that have a shape, a capitalised-word heuristic for names, a
per-conversation counter, `<TYPE_N>` placeholders, exact replacement back.
It is the honest baseline for «we added PII masking in an afternoon», and
the cases it is EXPECTED to miss are marked `hard` in the corpus.
"""

import re
from dataclasses import dataclass, field

from agentmask_ru.adapters.base import MaskedView, Span, TwoPhaseSession

# Shapes with a shape. Order matters: the longest, most specific patterns
# run first so a card number is not eaten by the bare-digits phone rule.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("CARD", re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")),
    ("SNILS", re.compile(r"\b\d{3}-\d{3}-\d{3} ?\d{2}\b")),
    ("PHONE", re.compile(r"(?:\+7|\b8)[\s\-()]*\d{3}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}\b")),
    ("INN", re.compile(r"\b\d{12}\b")),
    ("PASSPORT", re.compile(r"\b\d{2} ?\d{2} ?\d{6}\b")),
    ("DOB", re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b")),
    # «Фамилия Имя» in a form — two capitalised Cyrillic words. A naive
    # detector has no way to tell this from a company or a street name, and
    # no way at all to find a lower-case name, which is the point.
    ("NAME", re.compile(r"\b[А-ЯЁ][а-яё]{2,}(?:\s+[А-ЯЁ][а-яё]{2,}){1,2}\b")),
    ("ADDRESS", re.compile(
        r"(?:(?:ул|пер|просп|пр-д|наб|б-р|ш|пл|ал|туп)\.\s*|(?:улиц[аы]|переулок|проспект|шоссе|бульвар|набережная|площадь|проезд)\s+)"
        r"[^,.;\n]{2,40}(?:,?\s*(?:д\.?|дом)?\s*\d+[а-я]?)?(?:,?\s*(?:кв\.?|квартира)\s*\d+)?",
        re.IGNORECASE,
    )),
)


@dataclass
class NoopSession(TwoPhaseSession):
    def mask(self, messages: list[dict[str, object]], tools: list[dict[str, object]]) -> MaskedView:
        return MaskedView(messages=[dict(m) for m in messages], tools=[dict(t) for t in tools])

    def restore_arguments(self, arguments: str) -> str:
        return arguments


class NoopMasker:
    name = "noop"
    config: dict[str, object] = {}

    def open(self, case_id: str) -> NoopSession:
        return NoopSession()


@dataclass
class PlaceholderSession(TwoPhaseSession):
    """A per-conversation map from value to `<TYPE_N>` and back.

    Keeping the map for the whole conversation is the generous reading of
    «naive»: a per-request version would score worse on consistency, and the
    benchmark's floor should not be lower than what a careful afternoon
    produces.
    """

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
        taken: list[tuple[int, int]] = []

        def free(start: int, end: int) -> bool:
            return all(end <= s or start >= e for s, e in taken)

        out = text
        for kind, pattern in _PATTERNS:
            for match in list(pattern.finditer(text)):
                if not free(match.start(), match.end()):
                    continue
                taken.append((match.start(), match.end()))
                out = out.replace(match.group(0), self._placeholder(kind, match.group(0)))
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
            # Exact replacement straight into the serialised JSON — the way
            # every naive implementation does it, quotes and all.
            out = out.replace(token, value)
        return out

    def spans(self, text: str) -> list[Span]:
        found: list[Span] = []
        taken: list[tuple[int, int]] = []
        for kind, pattern in _PATTERNS:
            for match in pattern.finditer(text):
                if all(match.end() <= start or match.start() >= end for start, end in taken):
                    taken.append((match.start(), match.end()))
                    found.append(Span(start=match.start(), end=match.end(), type=kind))
        return sorted(found, key=lambda span: span.start)


class PlaceholderMasker:
    name = "placeholder_regex"
    config: dict[str, object] = {"patterns": [kind for kind, _ in _PATTERNS], "scope": "conversation"}

    def open(self, case_id: str) -> PlaceholderSession:
        return PlaceholderSession()
