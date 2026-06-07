"""Context-aware false-positive suppression (the deny-context layer Presidio lacks).

A bare numeric run that looks like a phone but sits next to an order/track/sum
word — with no phone cue — is not a phone. We drop it. Checksum-validated IDs
are never touched here (they're handled by priority in detect_all).
"""

import re

from obscura.detect import Span

# Words that, directly before a number, mean it is NOT a phone — either a non-PII
# code (order/track/amount) or a DIFFERENT PII type handled by its own detector
# (паспорт/инн/снилс/счёт/полис). Dropping the PHONE label here is safe: it is
# either not PII, or the right detector already tagged it.
_DENY = (
    "трек", "заказ", "артикул", "сумма", "руб", "чек", "талон", "sku", "№", "арт",
    "паспорт", "инн", "снилс", "счёт", "счет", "imei", "имей", "полис", "омс",
)
# Cues that a nearby number IS a phone.
_PHONE_TRIGGER = ("тел", "моб", "звон", "ватсап", "whatsapp", "вайбер", "перезвон", "контакт")
_LAST_WORD = re.compile(r"([а-яёa-z]+)[\s№:.\-]*$")

# Location-as-PII rule (HIPAA granularity x GDPR/152-ФЗ person-link).
# Region/country alone is never PII. A bare city is PII only when tied to a
# person (delivery/address/residence intent), not as a place reference.
_REGIONS = {
    "россия", "рф", "область", "край", "республика", "округ", "регион",
    "сибирь", "урал", "поволжье", "кавказ", "подмосковье",
}
_ADDR_INTENT = (
    "адрес", "доставк", "доставьте", "достав", "привез", "прописан",
    "проживает", "живу", "живёт", "живет", "заберите", "на улиц", "мне на",
    "мой адрес", "куда ехать", "забронир",
)
_PLACE_REF = (
    "час", "режим", "филиал", "магазин", "офис", "находит", "погод",
    "курс", "работаете", "есть ли", "ближайш",
)


def location_is_pii(text: str, start: int, end: int, value: str) -> bool:
    """True if a (bare, NER-found) location is tied to a person -> personal data.
    Street+house addresses are handled separately and always masked."""
    low = value.strip().lower()
    if low in _REGIONS or low.endswith(("область", "край", "округ")):
        return False  # region/country granularity -> not PII
    window = text[max(0, start - 30): end + 15].lower()
    if any(trigger in window for trigger in _ADDR_INTENT):
        return True  # person-linked place -> PII
    if any(trigger in window for trigger in _PLACE_REF):
        return False  # place reference (hours/branch/weather) -> not PII
    return False  # bare toponym with no person-link -> not PII (HIPAA/GDPR)


def suppress(text: str, spans: list[Span]) -> list[Span]:
    kept: list[Span] = []
    for span in spans:
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
            deny = any(last_word.startswith(word) for word in _DENY)
            cue = any(word in window for word in _PHONE_TRIGGER)
            if deny and not cue:
                continue
        kept.append(span)
    return kept
