"""Layer 1: PII detection in JSON / key:value forms.

Free-text NER stumbles on structure (e.g. a surname inside `{"имя":"Анна Смирнова"}`).
Here the KEY types the whole VALUE deterministically (имя->NAME, телефон->PHONE),
so the entire value is masked. Offsets are taken straight from the regex match
(no remap needed). Mirrors Presidio's BatchAnalyzer key-as-context idea.
"""

import re

from pseudex import morph_places
from pseudex.assets import ASSETS, StructuredAssets
from pseudex.detect import PartSpan, Span

# A filename/extension or a path separator. No person's name contains either, so
# rejecting these is free of recall risk.
_FILENAME_RE = re.compile(r"\.[A-Za-z0-9]{1,5}$|[/\\]")


def _is_filename(value: str) -> bool:
    return bool(_FILENAME_RE.search(value))


# A SENTENCE BOUNDARY INSIDE THE VALUE MEANS THIS WAS NEVER A FORM.
# «Никогда не выдумывай телефон, имя, адрес или email: бери их из сообщения
# дословно. Не задавай уточняющих вопросов…» — an ordinary instruction — parsed
# as a key of «адрес или email» over sixty characters of prose, and the stem
# «адрес» typed all of it as a place. The customer's own system prompt lost the
# sentence «не выдумывай телефон», the model duly invented one, and the invented
# value went to a tool. Over-masking manufactured data.
#
# The period is judged by what precedes it, because a form value is full of
# abbreviations that a naive rule would read as sentence ends: «Г. САНКТ-
# ПЕТЕРБУРГ» and «Д.7» are one letter and a dot, while «дословно.» is a word.
_SENTENCE_BREAK = re.compile(r"[А-Яа-яЁёA-Za-z]{2,}\.\s+[А-ЯЁA-Z]")


_NOT_IN_A_NAME = frozenset({"из", "в", "во", "на", "и", "или", "с", "со", "по", "у", "к", "ко", "от", "для", "за",
                            "о", "об", "про", "оба", "обе", "не", "the", "and"})


def _name_shaped(value: str) -> bool:
    words = value.replace("-", " ").split()
    return (1 <= len(words) <= 4 and not any(ch.isdigit() for ch in value)
            and not any(word.lower() in _NOT_IN_A_NAME for word in words))


def _is_running_text(value: str) -> bool:
    return bool(_SENTENCE_BREAK.search(value))


# The key->type map is LEASED (pseudex/assets.py); the shapes below are the
# structure of JSON and of a form field, not tuned vocabulary.
# Types whose value is meaningless without digits.
_NUMERIC_KEY_TYPES = frozenset({"PHONE", "SNILS", "INN", "CARD", "PASSPORT"})
_JSON_KV = re.compile(r'"([^"\s][^"]*?)"\s*:\s*"([^"]*?)"')
# A form value ends at a newline, a comma, a semicolon — OR AT THE NEXT KEY.
# The last clause was missing, and a 1C export puts every pair on ONE line:
# «Номер телефона для связи: +7 (931) 256 - 07 - 70 Дата доставки: Завтра» typed
# the phone AND the words after it as one PHONE, so the fake swallowed «Дата
# доставки», the model never saw that field, and detokenisation handed the tool
# a phone number with a sentence glued to it.
#
# The next key must start with a LETTER, which is what keeps «с 18:00 до 21:00»
# out: a time is introduced by digits and cannot look like a key.
_KEY_SHAPE = r"[А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z .\-]{1,24}?\s*:"
_FORM_KV = re.compile(
    r"([А-Яа-яЁёA-Za-z][А-Яа-яЁёA-Za-z .\-]{1,24}?)\s*:\s*"
    r"((?:(?!\s+" + _KEY_SHAPE + r")[^\n,;]){2,60})"
)
_KEY_CLEAN_RE = re.compile(r"[\s\-_.]")


def _key_type(key: str, structured: StructuredAssets) -> str | None:
    normalized = _KEY_CLEAN_RE.sub("", key.strip().lower())
    if normalized in structured.key_type:
        return structured.key_type[normalized]
    for stem, entity_type in structured.key_stems:
        if normalized.startswith(stem):
            return entity_type
    return None


_ADDRESS_ROLES = frozenset({"city", "street", "house", "flat", "entrance", "floor", "building"})


def _brace_events(text: str) -> list[tuple[int, int]]:
    """Every `{` (with a fresh object id) and `}` (id 0) outside JSON strings."""
    events: list[tuple[int, int]] = []
    next_id = 1
    in_string = False
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if in_string:
            if char == "\\":
                i += 2
                continue
            if char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            events.append((i, next_id))
            next_id += 1
        elif char == "}":
            events.append((i, 0))
        i += 1
    return events


def _by_object(text: str, matches: list[re.Match[str]]) -> dict[int, list[re.Match[str]]]:
    """The pairs grouped by the INNERMOST object each sits in."""
    events = _brace_events(text)
    stack: list[int] = []
    groups: dict[int, list[re.Match[str]]] = {}
    cursor = 0
    for match in matches:
        while cursor < len(events) and events[cursor][0] < match.start():
            _, object_id = events[cursor]
            cursor += 1
            if object_id:
                stack.append(object_id)
            elif stack:
                stack.pop()
        if stack:
            groups.setdefault(stack[-1], []).append(match)
    return groups


def _address_object_spans(text: str, matches: list[re.Match[str]],
                          claimed: set[int]) -> list[Span]:
    """AN OBJECT WITH A STREET AND A HOUSE IS ONE ADDRESS, whatever else it
    holds. Each leaf becomes a part of ONE substitute (see `PartSpan`); the
    street and the house are required because a city or a flat alone is not
    an address, and a street without a house is a street."""
    spans: list[Span] = []
    for group in _by_object(text, matches).values():
        leaves: dict[str, re.Match[str]] = {}
        for match in group:
            role = morph_places.role_of_field(match.group(1))
            if role in _ADDRESS_ROLES and match.group(2).strip() and role not in leaves:
                leaves[role] = match
        if "street" not in leaves or "house" not in leaves:
            continue
        whole = morph_places.address_from_fields(
            {role: match.group(2).strip() for role, match in leaves.items()})
        for role, match in leaves.items():
            raw = match.group(2)
            lead = len(raw) - len(raw.lstrip())
            value = raw.strip()
            start = match.start(2) + lead
            spans.append(PartSpan(start, start + len(value), "LOC", value, whole, role))
            claimed.add(match.start())
    return spans


def detect_structured_kv(text: str) -> list[Span]:
    """Detect PII by typing whole values from their key name."""
    structured = ASSETS.get().structured
    json_matches = list(_JSON_KV.finditer(text))
    claimed: set[int] = set()
    spans: list[Span] = _address_object_spans(text, json_matches, claimed)
    for regex in (_JSON_KV, _FORM_KV):
        for match in regex.finditer(text):
            if regex is _JSON_KV and match.start() in claimed:
                continue
            entity_type = _key_type(match.group(1), structured)
            if entity_type is None:
                continue
            raw = match.group(2)
            lead = len(raw) - len(raw.lstrip())
            value = raw.strip()
            if len(value) < 2:
                continue
            if _is_running_text(value):
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
            # A NAME VALUE HAS THE SHAPE OF A NAME. «клиенты: сидоров иван из
            # самары и петрова анна из казани» — the key typed the whole clause
            # as ONE person: two customers and their cities became a nine-word
            # substitute, the cities vanished from the model's view, and the
            # count by city the agent was asked for had nothing to count. A
            # person is at most four words with no preposition or conjunction
            # between them; anything wider is prose for the name arms to read.
            if entity_type == "NAME" and not _name_shaped(value):
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
