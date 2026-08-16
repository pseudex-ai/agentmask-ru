"""Context-aware false-positive suppression (the deny-context layer Presidio lacks).

A bare numeric run that looks like a phone but sits next to an order/track/sum
word — with no phone cue — is not a phone. We drop it. Checksum-validated IDs
are never touched here (they're handled by priority in detect_all).
"""

import re

from pseudex.assets import ASSETS, ContextAssets
from pseudex.detect import Span

# The deny list, the phone cues, the region set and the address/place vocabulary
# are LEASED (pseudex/assets.py). This module holds the rules that read them.
_LAST_WORD = re.compile(r"([а-яёa-z]+)[\s№:.\-]*$")

# Labels that name a KIND of identifier rather than a person. Kept here rather
# than in the leased vocabulary because they are published abbreviations, not
# tuned data — the same split the rest of the engine follows.
_DENY_AS_NAME = frozenset({
    "инн", "снилс", "огрн", "огрнип", "кпп", "бик", "омс", "дмс", "паспорт",
    "имей", "imei", "sku", "id", "гост", "ту", "фио", "адрес", "телефон",
})
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
            # The cue window is TIGHT, and that is the fix for a real confusion:
            # in «Паспорт 34 78 570405, выдан отделом, контакт +7…» the word
            # «контакт» belongs to the OTHER number thirty characters away, but
            # a wide window let it rescue the passport — which was then masked
            # as a phone. The value stayed protected, so nothing leaked, but the
            # TYPE was wrong, and the type is what the customer sees in their
            # journal and what decides which fake shape is minted.
            #
            # Adjacency beats proximity: a denying word DIRECTLY before the
            # number is stronger evidence than a cue somewhere nearby.
            window = text[max(0, span.start - 12): span.end + 12].lower()
            deny = any(last_word.startswith(word) for word in context.deny)
            cue = any(word in window for word in context.phone_trigger)
            if deny and not cue:
                continue
        if span.entity_type in ("PASSPORT", "OGRN"):
            # PASSPORT and OGRN are the identifiers with NO checksum to gate
            # them, so `1234 567890` matches a build number and a bare 15-digit
            # run matches an IMEI as readily as a real registration number.
            # Same rule as PHONE: a denying word directly before wins unless a
            # cue for the type itself is nearby.
            #
            # The asymmetry is deliberate. Missing a passport leaks personal
            # data; masking a version string only blinds the agent to something
            # it needed — so the cue is allowed to rescue the span, and only an
            # explicit non-PII word suppresses it.
            match = _LAST_WORD.search(text[:span.start].lower())
            last_word = match.group(1) if match else ""
            window = text[max(0, span.start - 30): span.end + 30].lower()
            deny = any(last_word.startswith(word) for word in context.deny)
            cue = any(word in window for word in context.passport_trigger)
            if deny and not cue:
                continue
        if span.entity_type == "NAME":
            # An abbreviation that is itself a non-PII marker is not a person.
            # `ИНН` in «СНИЛС …, ИНН 7672423881» was read as a name: it is
            # capitalised, it is not a dictionary word, and the name gazetteer
            # has no reason to refuse it. Masking it replaces a label the model
            # needs in order to know what the number beside it is.
            if span.value.strip().casefold() in _DENY_AS_NAME:
                continue
        kept.append(span)
    return kept
