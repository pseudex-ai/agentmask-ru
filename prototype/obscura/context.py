"""Context-aware false-positive suppression (the deny-context layer Presidio lacks).

A bare numeric run that looks like a phone but sits next to an order/track/sum
word — with no phone cue — is not a phone. We drop it. Checksum-validated IDs
are never touched here (they're handled by priority in detect_all).
"""

import re

from obscura.assets import ASSETS, ContextAssets
from obscura.detect import Span

# The deny list, the phone cues, the region set and the address/place vocabulary
# are LEASED (obscura/assets.py). This module holds the rules that read them.
_LAST_WORD = re.compile(r"([а-яёa-z]+)[\s№:.\-]*$")
_REGION_SUFFIXES = ("область", "край", "округ")


def location_is_pii(text: str, start: int, end: int, value: str) -> bool:
    """True if a (bare, NER-found) location is tied to a person -> personal data.
    Street+house addresses are handled separately and always masked.

    Location-as-PII rule (HIPAA granularity x GDPR/152-ФЗ person-link):
    region/country alone is never PII; a bare city is PII only when tied to a
    person (delivery/address/residence intent), not as a place reference."""
    context = ASSETS.get().context
    low = value.strip().lower()
    if low in context.regions or low.endswith(_REGION_SUFFIXES):
        return False  # region/country granularity -> not PII
    window = text[max(0, start - 30): end + 15].lower()
    if any(trigger in window for trigger in context.addr_intent):
        return True  # person-linked place -> PII
    if any(trigger in window for trigger in context.place_ref):
        return False  # place reference (hours/branch/weather) -> not PII
    return False  # bare toponym with no person-link -> not PII (HIPAA/GDPR)


def _is_version_string(text: str, start: int, context: ContextAssets) -> bool:
    """A dotted-quad is a valid IPv4 AND a valid version/build string. Deny rather
    than require-a-cue, to stay consistent with the phone rule and with
    fail-closed: an IP with no context stays masked, and only a known non-PII
    framing releases it."""
    window = text[max(0, start - 20):start].lower()
    return any(cue in window for cue in context.version_ctx)


def suppress(text: str, spans: list[Span]) -> list[Span]:
    context = ASSETS.get().context
    kept: list[Span] = []
    for span in spans:
        if span.entity_type == "IP" and _is_version_string(text, span.start, context):
            continue
        if span.entity_type == "PHONE":
            # (a) a "phone" that is a slice of a longer digit run (e.g. the first
            # 11 digits of a 14-digit postal track) is not a phone.
            before = text[span.start - 1] if span.start > 0 else ""
            after = text[span.end] if span.end < len(text) else ""
            if before.isdigit() or after.isdigit():
                continue
            # (b) deny when the word DIRECTLY before is an ID/non-PII word
            # ("паспорт 4509…", "заказа 9676…") — unless a phone cue is present.
            match = _LAST_WORD.search(text[:span.start].lower())
            last_word = match.group(1) if match else ""
            window = text[max(0, span.start - 25): span.end + 25].lower()
            deny = any(last_word.startswith(word) for word in context.deny)
            cue = any(word in window for word in context.phone_trigger)
            if deny and not cue:
                continue
        kept.append(span)
    return kept
