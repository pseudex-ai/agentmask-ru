"""Layer 1: PII detection in JSON / key:value forms.

Free-text NER stumbles on structure (e.g. a surname inside `{"имя":"Анна Смирнова"}`).
Here the KEY types the whole VALUE deterministically (имя->NAME, телефон->PHONE),
so the entire value is masked. Offsets are taken straight from the regex match
(no remap needed). Mirrors Presidio's BatchAnalyzer key-as-context idea.
"""

import re

from obscura.assets import ASSETS, StructuredAssets
from obscura.detect import Span

# A filename/extension or a path separator. No person's name contains either, so
# rejecting these is free of recall risk.
_FILENAME_RE = re.compile(r"\.[A-Za-z0-9]{1,5}$|[/\\]")


def _is_filename(value: str) -> bool:
    return bool(_FILENAME_RE.search(value))


# The key->type map is LEASED (obscura/assets.py); the shapes below are the
# structure of JSON and of a form field, not tuned vocabulary.
# Types whose value is meaningless without digits.
_NUMERIC_KEY_TYPES = frozenset({"PHONE", "SNILS", "INN", "CARD", "PASSPORT"})
_JSON_KV = re.compile(r'"([^"\s][^"]*?)"\s*:\s*"([^"]*?)"')
_FORM_KV = re.compile(r'([А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z .\-]{1,24}?)\s*:\s*([^\n,;]{2,60})')
_KEY_CLEAN_RE = re.compile(r"[\s\-_.]")


def _key_type(key: str, structured: StructuredAssets) -> str | None:
    normalized = _KEY_CLEAN_RE.sub("", key.strip().lower())
    if normalized in structured.key_type:
        return structured.key_type[normalized]
    for stem, entity_type in structured.key_stems:
        if normalized.startswith(stem):
            return entity_type
    return None


def detect_structured_kv(text: str) -> list[Span]:
    """Detect PII by typing whole values from their key name."""
    structured = ASSETS.get().structured
    spans: list[Span] = []
    for regex in (_JSON_KV, _FORM_KV):
        for match in regex.finditer(text):
            entity_type = _key_type(match.group(1), structured)
            if entity_type is None:
                continue
            raw = match.group(2)
            lead = len(raw) - len(raw.lstrip())
            value = raw.strip()
            if len(value) < 2:
                continue
            # `name` is genuinely ambiguous: in English payloads it usually means
            # the name OF A THING, and agents pass `{"name": "ideas.txt"}`
            # constantly. Typing those as NAME rewrote the agent's own file
            # arguments into Russian personal names and broke tasks that had
            # nothing to do with PII.
            #
            # The gate is deliberately NARROW — a filename or path is the only
            # thing here that can NEVER be a person, so excluding it costs zero
            # recall. A wider "must look like a person" gate was tried and is
            # wrong: it silently stopped masking `{"name": "johnsecret"}`, i.e.
            # it traded a leak for precision, which is backwards in a fail-closed
            # gateway. Ambiguous bare words (`test`, `config`) therefore stay
            # masked — over-masking is the safe side of this trade.
            if entity_type == "NAME" and _is_filename(value):
                continue
            # Key matching is prefix-based, so a compound key can pick up the
            # wrong stem: `cardholder_name` starts with `card` and was typed
            # CARD, which replaced a person's NAME with a fake CARD NUMBER — the
            # model then saw a card number where a name belongs.
            #
            # A numeric type whose value carries no digits is always mistyped.
            # It is NOT dropped, though: the customer put that value in a PII
            # field, so dropping it would trade a leak for tidiness. It is
            # demoted to the opaque type instead — still masked, but rendered as
            # REDACTED… rather than a fake number, and at the lowest overlap
            # priority so a recognizer that actually understands the value (NER
            # seeing a person's name) wins the span.
            if entity_type in _NUMERIC_KEY_TYPES and not any(c.isdigit() for c in value):
                entity_type = "OPAQUE"
            start = match.start(2) + lead
            spans.append(Span(start, start + len(value), entity_type, value))
    return spans
