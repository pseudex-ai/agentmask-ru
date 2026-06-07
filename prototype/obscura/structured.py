"""Layer 1: PII detection in JSON / key:value forms.

Free-text NER stumbles on structure (e.g. a surname inside `{"имя":"Анна Смирнова"}`).
Here the KEY types the whole VALUE deterministically (имя->NAME, телефон->PHONE),
so the entire value is masked. Offsets are taken straight from the regex match
(no remap needed). Mirrors Presidio's BatchAnalyzer key-as-context idea.
"""

import re

from obscura.detect import Span

_KEY_TYPE: dict[str, str] = {
    "имя": "NAME", "фио": "NAME", "клиент": "NAME", "заказчик": "NAME",
    "получатель": "NAME", "name": "NAME",
    "телефон": "PHONE", "тел": "PHONE", "моб": "PHONE", "мобильный": "PHONE",
    "номертелефона": "PHONE", "phone": "PHONE", "контактныйтелефон": "PHONE",
    "снилс": "SNILS", "snils": "SNILS",
    "инн": "INN", "inn": "INN",
    "паспорт": "PASSPORT", "passport": "PASSPORT",
    "карта": "CARD", "карты": "CARD", "card": "CARD",
    "почта": "EMAIL", "email": "EMAIL", "мейл": "EMAIL", "емейл": "EMAIL",
    "адрес": "LOC", "address": "LOC",
}
_JSON_KV = re.compile(r'"([^"\s][^"]*?)"\s*:\s*"([^"]*?)"')
_FORM_KV = re.compile(r'([А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z .\-]{1,24}?)\s*:\s*([^\n,;]{2,60})')


def _key_type(key: str) -> str | None:
    normalized = re.sub(r"[\s\-_.]", "", key.strip().lower())
    if normalized in _KEY_TYPE:
        return _KEY_TYPE[normalized]
    for stem, entity_type in _KEY_TYPE.items():
        if normalized.startswith(stem):
            return entity_type
    return None


def detect_structured_kv(text: str) -> list[Span]:
    """Detect PII by typing whole values from their key name."""
    spans: list[Span] = []
    for regex in (_JSON_KV, _FORM_KV):
        for match in regex.finditer(text):
            entity_type = _key_type(match.group(1))
            if entity_type is None:
                continue
            raw = match.group(2)
            lead = len(raw) - len(raw.lstrip())
            value = raw.strip()
            if len(value) < 2:
                continue
            start = match.start(2) + lead
            spans.append(Span(start, start + len(value), entity_type, value))
    return spans
