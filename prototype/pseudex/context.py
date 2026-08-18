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


# Types whose presence means the sentence is ABOUT a person. Deliberately
# excludes IP, MAC, PLATE, SECRET and VIN: a server, a device, a car or a key is
# not a person, and a release date beside a MAC address is still a release date.
_IDENTIFIES_A_PERSON = frozenset({
    "NAME", "SNILS", "INN", "PASSPORT", "INTL_PASSPORT", "CARD", "ACCOUNT",
    "PHONE", "EMAIL", "OMS", "BIRTH_CERT", "DRIVER_LICENSE", "AGE", "MEDICAL",
})


def _near_match(word: str, target: str) -> bool:
    """`word` is `target` with at most one letter inserted, deleted or changed.

    Deny words are typed by customers, and a customer who mistypes «договор» as
    «догвор» disables the guard that word exists to provide — the number beside
    it then becomes somebody's passport or phone. Measured on AgentPII-RU's
    sloppy register, that single typo class was most of the remaining false
    masks.

    Bounded deliberately at ONE edit and at a prefix match: two edits starts
    matching unrelated words, and a deny list that matches too much is a recall
    hole rather than a precision fix.
    """
    if abs(len(word) - len(target)) > 1:
        return False
    if word[:2] != target[:2]:
        return False
    i = j = 0
    edits = 0
    while i < len(word) and j < len(target):
        if word[i] == target[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(word) > len(target):
            i += 1
        elif len(word) < len(target):
            j += 1
        else:
            i += 1
            j += 1
    return edits + (len(word) - i) + (len(target) - j) <= 1


def _denied_nearby(word: str, deny: tuple[str, ...]) -> bool:
    """Deny-word match tolerant of one typo, on a stem-prefix basis."""
    return any(word.startswith(term) or _near_match(word, term) for term in deny)


def _passport_is_evidenced(text: str, span: Span, context) -> bool:
    """A passport number needs POSITIVE evidence, not merely the absence of a
    denying word.

    `NNNN NNNNNN` has no checksum and is the shape of an order pair, a part
    number and a price line. The gate used to be "mask unless a deny word sits
    directly before", which fails open twice over: a deny word we did not think
    of, and — measured on AgentPII-RU's sloppy register — a deny word the
    customer MISSPELT. «догвор 9455 480555р» has no recognisable «договор» in it,
    so the number pair became somebody's passport.

    Requiring a passport cue instead fails closed. The same reasoning already
    governs INN-10, the other identifier whose checksum is too weak to stand
    alone."""
    window = text[max(0, span.start - 40): span.end + 20].lower()
    return any(trigger in window for trigger in context.passport_trigger)


def _date_is_personal(text: str, span: Span, spans: list[Span]) -> bool:
    """Whether a bare numeric date is a quasi-identifier or just a date.

    A date alone identifies nobody. It becomes personal data by ASSOCIATION —
    next to a person, or next to a word saying it is a birth. Every other date in
    business writing is a document date: «Счёт 1234 от 15.05.2025», «Договор 8871
    от 02.09.2024», «Резервная копия от 15.05.2025».

    Those were all masked, because numeric dates had no gate at all while dates
    written out in words did. Measured on ordinary business sentences containing
    no personal data whatsoever, six of every eight false masks were this.

    A deny-list of document words was the other candidate and is worse: it has to
    grow forever (счёт, договор, накладная, платёж, релиз, отгрузка, акт…) and it
    fails open — a document word we did not think of masks the date. This gate
    fails CLOSED in the direction that matters: no person nearby, no masking.
    """
    # A date inside a URL is a path segment: rbc.ru/politics/07/07/2016/… . Found
    # on real text, where every dated news link produced one.
    prefix = text[max(0, span.start - 60): span.start]
    if ("http" in prefix or "www." in prefix) and " " not in prefix[-30:]:
        return False
    quasi = ASSETS.get().quasi
    window = text[max(0, span.start - 60): span.end + 60].lower()
    if any(cue in window for cue in quasi.birth_ctx):
        return True
    # A document word DIRECTLY before the date wins over a person elsewhere in
    # the sentence. «Запишите на сервис автомобиль А123ВС77, владелец Иванов
    # Пётр, телефон +7…, заказ-наряд от 10.06.2025» carries both: the naryad's
    # date is not the owner's birthday, and the owner is only nearby because the
    # sentence is about him. Association alone masked every one of these —
    # 172 of 1296 negatives on AgentPII-RU, all of this exact shape.
    #
    # The window is SHORT and looks only backwards, for the same reason the phone
    # cue window is tight: adjacency is evidence, proximity is not.
    lead = text[max(0, span.start - 26): span.start].lower()
    if any(word in lead for word in ASSETS.get().context.deny):
        return False
    # ANY personal identifier nearby makes the date theirs — not just a name.
    # The golden set showed why: «Реквизиты: СНИЛС 647-436-713 22, карта 4090…,
    # дата 21.01.1979» names nobody, yet the date is plainly that person's date
    # of birth. Gating on NAME alone dropped date recall to 48% on exactly those.
    # A document date has no identifier beside it — that is what separates them.
    return any(other.entity_type in _IDENTIFIES_A_PERSON
               and other.start < span.end + 80
               and other.end > span.start - 80
               for other in spans)


_SENTENCE_SPLIT = re.compile(r"[.!?\n]")


def _phone_shaped(value: str) -> bool:
    """Written the way a phone number is written, not merely eleven digits long.

    A leading «+», or eleven digits opening with 7 or 8. An order number, a
    track number and a passport all fail it, which is what keeps the rescue
    below from reopening the holes the deny gate was built to close.
    """
    digits = "".join(ch for ch in value if ch.isdigit())
    return value.lstrip().startswith("+") or (
        len(digits) == 11 and digits[0] in "78")


def _sentence_around(text: str, span: Span) -> str:
    """The sentence the span sits in — the unit a cue word actually belongs to."""
    start = 0
    for match in _SENTENCE_SPLIT.finditer(text[:span.start]):
        start = match.end()
    end = len(text)
    match = _SENTENCE_SPLIT.search(text, span.end)
    if match is not None:
        end = match.start()
    return text[start:end]


def suppress(text: str, spans: list[Span]) -> list[Span]:
    context = ASSETS.get().context
    kept: list[Span] = []
    for span in spans:
        if span.entity_type == "IP" and _is_version_string(text, span.start, context):
            continue
        if span.entity_type == "DATE" and not _date_is_personal(text, span, spans):
            continue
        if span.entity_type == "PASSPORT" and not _passport_is_evidenced(text, span, context):
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
            deny = _denied_nearby(last_word, context.deny)
            cue = any(word in window for word in context.phone_trigger)
            # A PHONE-SHAPED NUMBER IS RESCUED BY A CUE ANYWHERE IN THE SENTENCE,
            # not only inside the tight window. Real traffic writes «номер
            # телефона для заказа +7…» and «номер телефона указывали в заказах
            # 8916…»: the denying word «заказ» stands directly before the number
            # and won, so three real phones went to the model in the clear —
            # found in 993 production dialogues by comparing against an
            # independent detector.
            #
            # The tight window stays for everything else, because it was itself
            # a fix: in «Паспорт 34 78 570405, выдан отделом, контакт +7…» the
            # word «контакт» belongs to the OTHER number thirty characters away.
            # A passport is not phone-shaped — eleven digits opening with 7 or 8,
            # or a leading «+» — so it cannot reach this branch.
            # AN EXPLICIT «+» ENDS THE ARGUMENT. No order number, track number or
            # invoice is written «+79161112233»; the international prefix is a
            # statement that this is a telephone. Without this «аккаунт которого
            # обычно совершали заказ - +7…» stayed suppressed, because the
            # sentence held no phone cue at all — only the number's own shape.
            if deny and span.value.lstrip().startswith("+"):
                deny = False
            if deny and not cue and _phone_shaped(span.value):
                cue = any(word in _sentence_around(text, span).lower()
                          for word in context.phone_trigger)
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
            deny = _denied_nearby(last_word, context.deny)
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
