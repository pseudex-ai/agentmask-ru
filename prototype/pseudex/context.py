"""Context-aware false-positive suppression (the deny-context layer Presidio lacks).

A bare numeric run that looks like a phone but sits next to an order/track/sum
word — with no phone cue — is not a phone. We drop it. Checksum-validated IDs
are never touched here (they're handled by priority in detect_all).
"""

import re

from pseudex.fuzzy import within_one_typo

from pseudex.assets import ASSETS, ContextAssets
from pseudex import quasi as quasi_mod
from pseudex.detect import Span
from pseudex.json_fields import StringLeaf, string_leaves

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

# Words that introduce an ORGANISATION. A legal entity is not personal data —
# 152-ФЗ protects people — and replacing the customer's own supplier with an
# invented person removes the one word the model needed to know who is being
# talked about. «Это компания Весёлый Водовоз!» put 48 fake people into a
# thousand real dialogues.
#
# «ИП» is deliberately ABSENT: behind it stands a person's own ФИО, and the
# whole point of the type is that it names one.
# A one-word name written directly after a SMALL number is a UNIT, not a person.
# «(СИНЯЯ) -3 Бут» and «2 ЭТАЖ - 1 БУТ» are quantities of bottles; pymorphy3
# knows «Бут» as a genuine Russian surname, so morphology is right and only the
# number beside it says otherwise.
#
# BOUNDED AT THREE DIGITS, AND THE RUN MUST STAND ALONE. Written as «\d+» it
# matched the TAIL of any identifier, and the sloppy register puts a name
# straight after one: «карта 4177053773613102 СоколовИгорь», «машина М634АХ47
# ИвановПётр». Eight real names went unmasked on AgentPII-RU before the bound —
# the rule meant to remove eleven pieces of junk was quietly removing people.
#
# A dot breaks the match on purpose, so a numbered list («1. Иванов») keeps its
# person.
_QUANTITY_BEFORE = re.compile(r"(?:^|[^\w-])[-–—]?\s*\d{1,3}\s*$")


def _is_quantity(text: str, span: Span) -> bool:
    if len(span.value.split()) != 1:
        return False
    return bool(_QUANTITY_BEFORE.search(text[:span.start]))


def _is_organisation(text: str, span: Span) -> bool:
    """The word DIRECTLY before names a kind of company, not a person."""
    match = _LAST_WORD.search(text[:span.start].lower())
    return bool(match) and match.group(1) in ASSETS.get().context.org_cue


# A street type word beside the toponym. Kept here rather than in the leased
# vocabulary for the same reason `_DENY_AS_NAME` is: these are the published
# generic words, not tuned data.
_STREET_NEARBY = re.compile(
    r"\b(ул|улиц\w*|пр-?кт|проспект\w*|пер|переул\w*|б-р|бульвар\w*|ш|шоссе|"
    r"мкр|микрорайон\w*|д|дом|кв|квартир\w*|корп|стр|влад)\b", re.IGNORECASE)


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
    # THE CUE ALONE MAY NOT PROMOTE A BARE CITY, and that was the contradiction:
    # the paragraph above says city granularity identifies nobody, and then
    # «доставк» made it personal data anyway. «Я из Санкт-Петербурга, доставка
    # возможна?» is a question about the service area — masked 38 times across a
    # thousand real dialogues, one of the four over-masking classes the live
    # vault surfaced.
    #
    # A delivery address a person can be found at has a street or a house
    # number. Without either, the intent word is talking about a city, and a
    # city holds millions of people. Street+house addresses never reach this
    # function — they are the address layer's and are always masked — so nothing
    # that identifies anyone is released here.
    structured = any(char.isdigit() for char in window) or _STREET_NEARBY.search(window)
    if structured and any(trigger in window for trigger in context.addr_intent):
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
    return _passport_cue_in(window, context.passport_trigger)


def _passport_cue_in(window: str, triggers: tuple[str, ...]) -> bool:
    """A passport cue in the window — as written, stretched («паспоорт») or
    one typo away («паспрот»). THE CUE MAY BE DAMAGED and the detector already
    admitted the number on that damaged cue; both tests here must read the
    word the same way, or the span is found and then suppressed for lack of
    the cue it was found by — worse, «паспоорт» is one edit from the DENY
    word «паспорт» and was refused as a deny with no cue to save it."""
    if any(trigger in window for trigger in triggers):
        return True
    for token in re.findall(r"[а-яё]+", window):
        word = re.sub(r"([а-яё])\1+", r"\1", token)
        if len(word) >= 5 and (word.startswith("паспорт") or within_one_typo(word[:7], "паспорт")):
            return True
    return False


_PERSONNEL_HEAD: int = 40
# Words that introduce the SUBJECT — the person the record is about — not staff.
# A subject word anywhere in the window before a name beats a role word further
# back: «врач принял пациента Иванова» — Иванова is the subject even though
# «врач» sits earlier in the same sentence. Published subject words, kept in the
# engine like `quasi._PERSON_BEFORE_DATE_RE`, not leased tuning.
_SUBJECT_CUE = re.compile(
    r"(?<![а-яёa-z0-9])(?:пациент\w*|клиент\w*|ребён\w*|ребен\w*|"
    r"получател\w*|заказчик\w*|посетител\w*)(?![а-яёa-z0-9])",
    re.IGNORECASE)


def _name_is_personnel(text: str, span: Span) -> bool:
    """Whether a NAME is framed as STAFF (врач/специалист/должность), not the subject.

    A role word introducing the name — prose «врач Лапина Вера», or a JSON key
    `"doctor": {"name": "Лапина Вера"}` a few characters back — demotes it: the
    person is the one PROVIDING the service, so a date beside them is a meeting
    or slot date, not their date of birth. Only a role word in the SHORT window
    before the name counts, matched on whole words («врач» does not match
    «врачебный»). A subject word in the same window wins over the role word, so a
    patient named after a doctor is not demoted («врач принял пациента Иванова»).
    """
    head = text[max(0, span.start - _PERSONNEL_HEAD): span.start].lower()
    if _SUBJECT_CUE.search(head):
        return False
    for cue in ASSETS.get().context.personnel_cue:
        if re.search(r"(?<![а-яёa-z0-9])" + re.escape(cue) + r"(?![а-яёa-z0-9])", head):
            return True
    return False


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
    # A document/operational word DIRECTLY before the date wins over EVERYTHING
    # else, including a birth cue earlier in the sentence. «…родился 21.09.1955,
    # слот 2026-09-02» carries both: the slot date is not the owner's birthday,
    # and «родился» is only nearby because the sentence is about him. Association
    # alone masked every one of these — 172 of 1296 negatives on AgentPII-RU,
    # all of this exact shape. The window is SHORT and looks only backwards, for
    # the same reason the phone cue window is tight: adjacency is evidence,
    # proximity is not.
    lead = text[max(0, span.start - 26): span.start].lower()
    if any(word in lead for word in ASSETS.get().context.deny):
        return False
    # THE CUE MUST BE IN THE SAME SENTENCE. A host's own instruction says «…пол
    # пациента вычисли сам из даты рождения и имени. Сегодня 2026-09-02.»: the
    # cue belongs to the instruction and the date is TODAY. Masked, it moved the
    # model's notion of today and every relative date the agent computed moved
    # with it — the clinic slot was booked in March instead of September (r2
    # run, 10 triples, both controls agreeing). Same window, same rule as
    # `quasi._birth_context_near`; a period inside «д.р.» is not a sentence end.
    window = quasi_mod.sentence_window(text, span.start, span.end, 60, 60)
    if any(cue in window for cue in quasi.birth_ctx):
        return True
    # ANY personal identifier nearby makes the date theirs — not just a name.
    # The golden set showed why: «Реквизиты: СНИЛС 647-436-713 22, карта 4090…,
    # дата 21.01.1979» names nobody, yet the date is plainly that person's date
    # of birth. Gating on NAME alone dropped date recall to 48% on exactly those.
    # A document date has no identifier beside it — that is what separates them.
    #
    # A NAME is not evidence when it is STAFF: the doctor in a clinic-slot result
    # sits within 80 characters of every slot's datetime, and reading the doctor's
    # name as the subject made a meeting date read as a birth date — the slot got
    # a fake date and the model booked March instead of September (live run).
    # The subject is named by nothing or by a subject word; a role word demotes.
    for other in spans:
        if other.entity_type not in _IDENTIFIES_A_PERSON:
            continue
        if not (other.start < span.end + 80 and other.end > span.start - 80):
            continue
        if other.entity_type == "NAME" and _name_is_personnel(text, other):
            continue
        return True
    return False


# Слова-ВЕЩИ перед числом лет: «стаж 15 лет», «опыт 28 лет», «гарантия 3 года».
# Целыми словами, в отличие от общего DENY (там «ту» подстрокой бьёт «пациенту»).
_AGE_DENY = re.compile(
    r"(?i)(?:^|[^а-яёa-z0-9])(?:опыт\w*|стаж\w*|выслуг\w*|гарант\w*|подписк\w*"
    r"|аренд\w*|срок\w*|более|менее|спустя|через)\s*$")
# Сравнительное слово ПОСЛЕ числа: «на 10 лет моложе Зюганова» — это СРАВНЕНИЕ,
# не возраст. Без него «Зюганова» (имя в 80 знаках) легализует «10 лет» как его
# возраст (NEREL precision: «10 лет моложе»).
_AGE_COMPARE_TAIL = re.compile(
    r"(?i)^\s*(?:моложе|старше|младше|раньше|позже|меньше|больше)\b")
# Дательный падеж местоимений/субъектов ПЕРЕД числом возраста («ему/ей/мне»,
# «пациенту/клиенту»); «исполнилось» допущено как мостик.
_AGE_PERSON = re.compile(
    r"(?i)(?:^|[^а-яёa-z0-9])(?:ему|ей|мне|тебе|им|нам|пациент\w*|клиент\w*"
    r"|реб[её]н\w*|посетител\w*|получател\w*|заказчик\w*)(?:\s+исполнил\w+)?\s*$")


def _age_is_personal(text: str, span: Span, spans: list[Span]) -> bool:
    """Whether a bare «N лет» is the subject's age or a thing's («опыт/стаж»).

    Возраст — ПД по ассоциации с человеком (152-ФЗ), а не по величине числа:
    «ему 28 лет» и «Иванов, 28 лет» — про человека, «зданию 92 года» и
    «опыт 28 лет» — нет. Тот же сигнал, что и у даты: местоимение/субъект
    прямо перед числом, либо любой идентификатор человека в окне. Сам возраст
    свидетельством человека не является (иначе «опыт 28 лет» сам себя бы
    легализовал).
    """
    before = text[max(0, span.start - 24):span.start].lower()
    # A thing-word directly before («опыт/стаж/гарантия») denies the age even
    # beside a name: «Иванов, стаж 15 лет» is tenure, not the person's age.
    # WHOLE-WORD, not the shared DENY's substring list («ту» in «пациенту»).
    lead = text[max(0, span.start - 26):span.start].lower()
    if _AGE_DENY.search(lead):
        return False
    # A comparative word right AFTER («на 10 лет моложе») is a comparison, not
    # the person's age — deny before the name association below fires.
    tail = text[span.end:span.end + 16].lower()
    if _AGE_COMPARE_TAIL.search(tail):
        return False
    if _AGE_PERSON.search(before):
        return True
    for other in spans:
        if other.entity_type not in _IDENTIFIES_A_PERSON or other.entity_type == "AGE":
            continue
        if not (other.start < span.end + 80 and other.end > span.start - 80):
            continue
        if other.entity_type == "NAME" and _name_is_personnel(text, other):
            continue
        return True
    return False


_SENTENCE_SPLIT = re.compile(r"[.!?\n]")


def _phone_shaped(value: str) -> bool:
    """Written the way a phone number is written, not merely eleven digits long.

    A leading «+», or eleven digits opening with 7 or 8. An order number, a
    track number and a passport all fail it, which is what keeps the rescue
    below from reopening the holes the deny gate was built to close.
    """
    digits = "".join(ch for ch in value if ch.isdigit())
    if value.lstrip().startswith("+") or (len(digits) == 11 and digits[0] in "78"):
        return True
    # A DICTATED PHONE HAS NO DIGITS TO BE SHAPED LIKE, and the rescue below —
    # «a phone cue anywhere in the sentence beats a denying word» — was gated on
    # this test, so it never ran for one. «телефон для чека восемь девятьсот
    # шестнадцать…» has the cue two words away and the deny word «чек» directly
    # before, and the number went to the model IN THE CLEAR. Fifteen of 2444
    # values on the first `long_bank` run, in the one place 54-ФЗ makes a phone
    # mandatory.
    #
    # Safe because the span is already typed. Only `spoken.detect_spoken_ids`
    # produces a digit-free PHONE, and it produces one only after `run_to_digits`
    # yielded eleven digits opening 7 or 8 followed by 9 — the same test this
    # function makes, applied to the digits the words decode to. A passport,
    # an order number or a track number cannot arrive here without a digit.
    return not any(ch.isdigit() for ch in value) and bool(value.strip())


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


def _date_in_own_field(text: str, span: Span, spans: list[Span],
                       leaf: StringLeaf) -> bool:
    """A JSON date's evidence belongs to its own value or a typed ancestor.

    A patient's name in a SIBLING field cannot make an appointment slot their
    birthday. Equally, `dob: ["..."]` carries explicit evidence via its path,
    and a free-text note may carry a birth cue inside its own value.
    """
    from pseudex.structured import key_type
    if any(isinstance(key, str) and key_type(key) == "DOB" for key in leaf.path):
        return True
    local = Span(span.start - leaf.start, span.end - leaf.start,
                 span.entity_type, span.value)
    local_text = text[leaf.start:leaf.end]
    # Re-evaluate the original birth recognizer INSIDE this leaf. Its typo,
    # abbreviation and pronoun evidence is stronger than the generic DATE
    # association rule and must not be lost by enforcing field isolation.
    # Reusing it also avoids a second, inevitably drifting birth-cue dialect.
    if any(birth.entity_type == "DOB" and birth.start <= local.start
           and local.end <= birth.end for birth in quasi_mod.detect_quasi(local_text)):
        return True
    neighbours = [Span(other.start - leaf.start, other.end - leaf.start,
                       other.entity_type, other.value)
                  for other in spans
                  if leaf.start <= other.start and other.end <= leaf.end]
    return _date_is_personal(local_text, local, neighbours)


def suppress(text: str, spans: list[Span]) -> list[Span]:
    context = ASSETS.get().context
    kept: list[Span] = []
    # This is context attribution AFTER all recognizers ran, never a PII
    # pre-filter. Parse once per payload, not once per date or adjacent person.
    leaves = string_leaves(text) if any(s.entity_type in ("DATE", "DOB") for s in spans) else ()
    for span in spans:
        if span.entity_type in ("DATE", "DOB"):
            leaf = next((field for field in leaves
                         if field.start <= span.start and span.end <= field.end), None)
            if leaf is not None:
                if not _date_in_own_field(text, span, spans, leaf):
                    continue
                if span.entity_type == "DATE":
                    span = Span(span.start, span.end, "DOB", span.value)
        if span.entity_type == "IP" and _is_version_string(text, span.start, context):
            continue
        if span.entity_type == "DATE":
            # A DATE THE DENY LAYER KEEPS IS PERSONAL, AND PERSONAL MEANS DOB.
            # `_date_is_personal` answers «is this date a person's date or a
            # document date» — by a birth cue or by association with a subject
            # identifier — and it is the ONE signal, not a new heuristic. A
            # personal date kept as `DATE` leaked through the envelope's neutral
            # echo leg, which excludes `DATE` on purpose (a meeting/invoice date
            # must stay real): «Реквизиты: СНИЛС …, карта …, дата 21.01.1979»
            # typed the date `DATE`, so an unbound tool result echoing it reached
            # the model in the clear. Retyping the kept span to `DOB` makes the
            # vault mint a DOB fake and the echo leg redact its echo, while the
            # meeting date — which `_date_is_personal` rejects — still falls into
            # the `continue` below and stays real. `quasi` already emits `DOB`
            # for the birth-cue case; a duplicate DOB of the same span is dropped
            # by overlap resolution, so no new evidence path is opened.
            if _date_is_personal(text, span, spans):
                span = Span(span.start, span.end, "DOB", span.value)
            else:
                continue
        if span.entity_type == "AGE" and not _age_is_personal(text, span, spans):
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
            cue = _passport_cue_in(window, context.passport_trigger)
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
            if _is_quantity(text, span):
                continue
            if _is_organisation(text, span):
                continue
        kept.append(span)
    return kept
