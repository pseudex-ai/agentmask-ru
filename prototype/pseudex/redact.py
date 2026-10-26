"""The swap layer: tokenize text on the way to the model, detokenize on the way back.

Detection is decoupled — the caller passes the spans (from any detector), so the
proxy can use the full ensemble (regex + checksum + NER) and tests can use a
lighter one. Reverse uses longest-token-first to avoid prefix collisions.
"""

import json
import re
from typing import NamedTuple

from pseudex.detect import NameSpan, PartSpan, Span
from pseudex import (agent_form, cvc, morph_names, morph_places, notation,
                     ru_pii_v6, spoken, structured, translit)
from pseudex.assets import ASSETS
from pseudex.normalize import normalize
from pseudex.inspection import Edit
from pseudex.restoration import RestorationField
from pseudex.profiling import stage
from pseudex.vault import (LOC_TOKEN_PATTERN, REDACTION_MARKER, token_re, Vault, name_key,
                           place_key, _date_canonical, canonicalize, fold_key,
                           zero_grouped)

# A number-like run (digits + phone separators), >=7 digits — a candidate for
# digit-core detokenization when the model reformatted a numeric token.
# «/» joins the halves of a passport the model laid out as «0022 / 385996»
# (live v4: nine replies showed the customer a fake passport in a table).
_NUM_RUN = re.compile(r"(?<![\d])[+(]?\d[\d\s()./\-]{5,}\d(?!\d)")
# Значение поля целиком: только цифры и разделители, не меньше трёх цифр.
_WHOLE_NUMBER = re.compile(r"[+(]?\d[\d\s().\-]*\d(?:\D*)?")
# СКОЛЬКО ЦИФР ДЕЛАЮТ ЧИСЛО ЗНАЧЕНИЕМ, А НЕ КОЛИЧЕСТВОМ, когда его никто не
# назвал. Группа СНИЛС — три, серия и хвост телефона — четыре, а двузначное без
# подсказки — это «количество: 12». Порог один на оба направления: спрашивать о
# куске, о котором восстановление не спрашивало, значит докладывать об отказе,
# которого не было (`_still_a_whole_value`).
_FRAGMENT_DIGIT_FLOOR = 3


class _ResolvedSpan(NamedTuple):
    """A resolved owner keeps its type until replacement priority is chosen."""

    start: int
    end: int
    value: str
    entity_type: str
    bound_identity: bool = False


class _Whole:
    """Совпадение-заглушка для случая «всё поле — одно число»."""

    __slots__ = ("_start", "_end", "_text")

    def __init__(self, start: int, end: int, text: str) -> None:
        self._start, self._end, self._text = start, end, text

    def start(self) -> int:
        return self._start

    def end(self) -> int:
        return self._end

    def group(self) -> str:
        return self._text


def _splice(text: str, spans: list[tuple[int, int, str]]) -> str:
    """Apply replacements right-to-left so the offsets of the not-yet-applied
    spans stay valid."""
    result = text
    for start, end, value in sorted(spans, key=lambda span: span[0], reverse=True):
        result = result[:start] + value + result[end:]
    return result


def mask_text(text: str, vault: Vault, spans: list[Span],
              capture: list[Edit] | None = None,
              base_tokens: list[str] | None = None) -> str:
    """Replace detected PII with consistent tokens. Pure w.r.t. text; mutates vault.

    A span whose value is ALREADY a token we issued is left untouched. This is
    load-bearing, not defensive: a fake NAME or LOC is by construction a
    well-formed name or place, so when the model echoes one back inside a new
    message, detection finds it again. Masking it a second time would mint a
    fresh token, which (a) makes the person's identity change every turn, (b)
    breaks the provider's prefix cache because the prefix is no longer stable,
    and (c) — worst — makes detokenization return the intermediate TOKEN instead
    of the real value, so the tool executes on a plausible but WRONG person.

    The content cache hides this from the obvious test: re-masking the same RAW
    text is a cache hit. The failure only appears when the token comes back
    inside different surrounding text, which is exactly what a multi-turn agent
    does.

    KNOWN LIMIT: a real person whose name exactly equals a minted fake name would
    be passed through unmasked. That needs a fake-name pool far larger than the
    current seed list (see names.py) — the same production swap already planned."""
    replacements: list[tuple[int, int, str]] = []
    for index, span in enumerate(spans):
        if is_own_substitute(span, vault):
            continue
        shown = _token_for_text(span, vault)
        # REMEMBERED CHARACTER FOR CHARACTER: what this dialogue was shown
        # where the customer wrote what. The verbatim pass on the way back
        # (`_restore_verbatim_spans`) hands an agent that copied the shown
        # form the customer's literal string — see `Vault.shown_forms`. The
        # literal is the ORIGINAL text at the span, not `span.value`: the
        # detector reads the normalised text, where «бaбичев» has already lost
        # its Latin «a» and «682О» its Cyrillic «О», and offsets index the
        # original 1:1 by the normalisation invariant.
        literal = text[span.start:span.end]
        if _shown_mirrors(shown, literal, span.entity_type):
            vault.remember_shown(shown, literal, span.entity_type)
        replacements.append((span.start, span.end, shown))
        if capture is not None and shown != literal:
            # The audit loop already obtained the base token. Inspection must
            # never mint another one, or try to rediscover the shown form later.
            redaction = REDACTION_MARKER.fullmatch(shown) is not None
            base = base_tokens[index] if base_tokens is not None else None
            capture.append(Edit(span.start, span.end, shown, span.entity_type,
                                None if redaction else base,
                                "redaction" if redaction else "pseudonym"))
    return _splice(text, replacements)


def _shown_mirrors(shown: str, literal: str, entity_type: str) -> bool:
    """Whether this dialogue was shown a form worth remembering verbatim.

    Recorded for EVERY type now, addresses included: an agent that copies the
    shown substitute into a tool argument gets the customer's literal string
    back, character for character — «заболоцкого 81 кв 51» with no «улица», no
    comma, its own case, its own typo — which is exactly what it would have
    passed without us. The verbatim pass keys on the EXACT shown string, so it
    only ever fires on a true copy; a model that REWRITES the address writes a
    different string, misses the verbatim pass and falls to the form-rebuild
    below. The old rule refused to record a bare-street address (the substitute
    added «улица» the customer had not written) and returned our rebuilt form
    instead — 17 addresses scored as changed on the public benchmark. The
    substitute now mirrors the customer's form (`_fake_place`), so there is
    nothing to refuse."""
    return bool(shown) and shown != literal


def is_own_substitute(span: Span, vault: Vault) -> bool:
    """A detected span that is OURS coming back: the exact token, or an
    address the model composed around one. THE ONE RULE FOR THREE CALLERS —
    `mask_text`, the envelope's audit loop and the benchmark's scorer each
    filtered echoes on their own, and the second rule reached only one of
    them, so production and the instrument disagreed about the same text."""
    # ЗНАЧЕНИЕ, ОБЪЯВЛЕННОЕ ХОСТОМ СВОИМ, — не данные субъекта. Имя ассистента
    # («здравствуйте, Татьяна») и адрес компании («а вы на Ленина 14?») говорит
    # КЛИЕНТ, но принадлежат они не ему: замаскировав их, мы показываем модели
    # обращение к постороннему и чужой адрес, и агент отвечает «нет, мы на
    # Ленина 14» на вопрос, который сам же и не смог прочитать. Пусто по
    # умолчанию — см. `Vault.with_own_values`.
    if vault.is_own_value(span.value):
        return True
    # РЕДАКЦИЯ — НЕ ДАННЫЕ. The engine itself writes `REDACTED<6 hex>` where a
    # substitute cannot stand (an OPAQUE leaf, an echo with no binding), and the
    # marker's hex digits read as a NUMBER to the next pass: under a numeric field
    # key (`cardholder` → CARD) the engine minted a fake card over its own
    # redaction, so the one string that is supposed to be inert became a new value
    # on every request, and the model never saw the substitute it was given
    # (g07: `cardholder` → `REDACTED2aada2`). A marker is a fixed point of the
    # mask, like every other rendering of ours — see `vault.REDACTION_MARKER`.
    if REDACTION_MARKER.fullmatch(span.value):
        return True
    if vault.is_minted_token(span.value):
        return True
    if span.entity_type in {"PHONE", "SNILS", "INN", "CARD", "PASSPORT"} and not any(
            char.isdigit() for char in span.value):
        digits: str = re.sub(r"\D", "", canonicalize(span.entity_type, span.value))
        hit = vault.resolve_digit_signatures_typed({digits}, False).get(digits)
        if hit is not None and hit[0] == span.entity_type:
            return True
    # THE MODEL'S OWN DERIVATION OF OUR SUBSTITUTE IS OURS TOO. It wrote
    # «LEBEDEVA ALINA» into `name_latin` from the token it was given; that call
    # rides in the transcript, the Latin name detector found a person in it,
    # and the vault minted «Герман Тимур» for a string that was never anybody
    # (scripted v4, chain-028). The restorer already knows how to tell a
    # derivation of a token from a real Latin name — the same test decides here.
    if span.entity_type == "NAME" and _is_derived_surface(span.value):
        return _derived_owner(span.value, vault) is not None
    # CLASS В: THE IDENTITY QUESTION IS ASKED OF THE SURFACE, NOT OF THE TYPE.
    # The branches above are switches on `span.entity_type`, and the type is a
    # property of the FIELD, not of the value: `structured.detect_structured_kv`
    # types a leaf by its KEY (`cardholder` prefix-matches `card`), demotes a
    # numeric key type whose value has no digit to OPAQUE (`structured.py:216`),
    # and OPAQUE has no renderer — so the model read `REDACTED<hex>` where its own
    # substitute stood (g07). The type is gone by then; the IDENTITY is not, and
    # the vault is its only holder. A part, a lone surname, initials, an oblique
    # case and the other script are all renderings of ONE substitute this
    # dialogue showed, and they are answered here for every type at once — the
    # same one rule for `mask_text`, the envelope and the benchmark's scorer.
    #
    # LOC IS NOT ASKED, and that is not the type gate coming back. A place has
    # its OWN identity question with its own machinery (`place_fragment_is_ours`,
    # `holds_minted_place`, the `place_parts` index): «улица Шилова 12» is a real
    # address that happens to carry a person's surname, and passing it through
    # would put the customer's address in the clear. A NAME rendering is a person
    # by construction; a place is not, whatever it is spelled like.
    if span.entity_type != "LOC" and vault.name_rendering_is_ours(span.value):
        return True
    if isinstance(span, PartSpan) and span.entity_type != "LOC":
        # A FIELD OF A TYPED OBJECT IS JUDGED BY THE WHOLE OBJECT, exactly as the
        # address branch below judges it and for the same reason: leaf by leaf
        # nothing is a token (`{"passport": {"series": "0012", …}}` is two bare
        # four- and six-digit runs), so the record was minted a SECOND document
        # and the model watched its own substitute change. The whole is what the
        # vault minted and what its digit signature answers for.
        return span.whole != span.value and vault.is_minted_token(span.whole)
    if span.entity_type != "LOC":
        return False
    # A FIELD OF AN ADDRESS OBJECT IS JUDGED BY THE WHOLE OBJECT. The model's
    # own tool call — {"locality": "можга", "street": "кленовую", "building":
    # "112"} around the token it was given — rides in the transcript and is
    # re-masked with it; leaf by leaf nothing is a token, and the object was
    # minted a THIRD address (scripted v4: compare 14/42 -> 1/42 the day
    # address objects were introduced).
    whole = vault_value(span)
    return vault.holds_minted_place(whole) or (whole != span.value and vault.is_minted_token(whole))


def _document_part(span: PartSpan, vault: Vault) -> str:
    """ОДИН ЛИСТ ТИПИЗИРОВАННОГО ОБЪЕКТА — часть ЕГО подмены, в его форме.

    Серия и номер паспорта — не два документа, а один: поле получает СВОЮ часть
    подмены целого, иначе инструмент увидит серию одного человека и номер
    другого. Раскладка — по цифровой длине роли из арендуемой карты частей
    (`COMPOSITE_TYPES.lengths`), а не по догадке о форме значения.

    РОЛЬ, КОТОРУЮ ПОДМЕНА ПОКАЗАТЬ НЕ МОЖЕТ, ОТДАЁТ ЛИСТ ЦЕЛОЙ ПОДМЕНОЙ —
    ровно как у адреса (`_token_for_text`): fail closed, а не открытый лист.
    """
    composite = ASSETS.get().structured.composites.get(span.entity_type)
    token = vault.tokenize(span.whole, span.entity_type)
    if composite is None:
        return token
    digits = re.sub(r"\D", "", token)
    offset = 0
    for role in composite.order:
        size = composite.lengths.get(role, 0)
        if role == span.role:
            part = digits[offset:offset + size]
            return _digits_like(span.value, part) if part else token
        offset += size
    return token


def _digits_like(original: str, digits: str) -> str:
    """Цифры подмены в СВОИХ разделителях: лист написан так, как написан."""
    if not digits or len(re.sub(r"\D", "", original)) != len(digits):
        return digits
    stream = iter(digits)
    return "".join(next(stream) if ch.isdigit() else ch for ch in original)


def vault_value(span: Span) -> str:
    """What the vault keys for this span: the whole address for a field of
    one, the span's own text otherwise."""
    return span.whole if isinstance(span, PartSpan) else span.value


def tokenize_span(span: Span, vault: Vault) -> str:
    """The substitute the vault holds for this span — ONE entry for the
    masking, the audit and the benchmark's scorer, so a span that carries
    evidence (an address field, a governed name) is minted the same way
    wherever it is asked about."""
    if isinstance(span, NameSpan) and span.cases:
        return vault.tokenize_person(span.value, span.cases)
    return vault.tokenize(vault_value(span), span.entity_type)


def _agree_settlement(token: str, original: str) -> str:
    """The token's settlement in the case the original's settlement stands in.

    The settlement is real now, so the sentence reads it as a word: «Живу на
    Валдае, улица Мира 4» keeps a nominative street after an oblique city, and
    `detect_case` of the whole phrase says nominative. Only the city is bent."""
    case = morph_places.city_case(original)
    if case is None or case == "nomn":
        return token
    city = morph_places.split_roles(token).get("city", "")
    if not city:
        return token
    return token.replace(city, morph_places.inflect_place(city, case), 1)


# THE SETTLEMENT MARKERS `_SIGNATURE_NOISE` DOES NOT CARRY. That list is the
# vault INDEX and may not move — rows already minted hold keys built from it —
# but a settlement marker is exactly as structural as «д.» or «кв.»: it names a
# field, not a place. Its absence there is why «г. Ачинск, б-р Вишнёвый, д. 30»
# and «Ачинск, б-р Вишнёвый 30» got different keys and a flawless mirror was
# refused. Local to this check, one line of it, so the index stays where it is.
_SETTLEMENT_MARKERS = frozenset({"г", "гор", "город", "с", "пос"})
_DIGIT_RUN = re.compile(r"\d+")


def _mirror_leaks_nothing(shown: str, agreed: str) -> bool:
    """Whether the mirrored form shows the model nothing real.

    THE PROPERTY IS ABOUT THE WHOLE VALUE, NOT ABOUT WORDS. The shown string must
    READ BACK to the fake — the same address parts, the same numbers — because a
    notation legitimately rewrites its numbers as words and a comparison by WORD
    SETS cannot see that: «шесть» and «сто тридцать два» are not words of the
    fake, they are its digits SPOKEN, and the guard called a flawless dictated
    mirror a leak. That false red is what made `LOC spoken` 0 of 26 while the
    phone was 26 of 26 (g01 P1): the renderer worked, the mirror was refused.

    What it still refuses is what matters: a real street word surviving gives a
    different role, a real house or flat surviving gives a different NUMBER, and
    either one flips the comparison to False and the safe canonical fake is
    shown instead. The generic word is the agent's own («проспект» where the fake
    carries «улица») and is dropped by the shared reader, not by a second list."""
    if not shown or not agreed:
        return False
    theirs = _place_values(shown)
    ours = _place_values(agreed)
    if not ours or theirs != ours:
        return False
    return _spoken_numbers(shown) <= _spoken_numbers(agreed)


def _place_values(phrase: str) -> dict[str, str]:
    """An address as a VALUE: role -> its content, numbers read as digits.

    Names are compared by signature (stems, order-free) and numbers by
    `house_digits` — the same readers the vault keys and the restorer renders
    with, so the guard cannot drift from what it guards."""
    values: dict[str, str] = {}
    for role, part in morph_places.split_roles(phrase).items():
        # ПОД-РОЛИ УЛИЦЫ НЕ СРАВНИВАЮТСЯ ЗДЕСЬ: тип — оформление, которое
        # зеркало ВПРАВЕ менять (клиент написал «ул.», подмена — «улица»), и
        # сравнение написаний отказывало бы безупречное зеркало ровно за то, что
        # оно зеркало. Содержимое улицы уже сравнивается сигнатурой ниже.
        if role in morph_places._STREET_SUB_ROLES:
            continue
        values[role] = (morph_places.match_signature(part)
                        if role in ("street", "city")
                        else _fold_word(morph_places.house_digits(part)))
    return values


def _spoken_numbers(phrase: str) -> set[str]:
    """Every number the phrase names, with numeral runs read back to digits.

    Read by `_fold_cardinals`, the reader the vault already uses to compare two
    houses one of which was dictated — a second words-to-digits rule here would
    disagree with it on exactly the forms it was written for."""
    tokens = re.findall(r"[А-Яа-яЁё]+|\d+", phrase)
    return set(_DIGIT_RUN.findall(" ".join(morph_places._fold_cardinals(tokens))))


def _fold_word(word: str) -> str:
    """One spelling for the comparison: «Ё» is «е» and case does not count."""
    return word.casefold().replace("ё", "е")


def _token_for_text(span: Span, vault: Vault) -> str:
    """The token as it should READ in this sentence.

    The vault stores one nominative token per person; the text needs it in the
    case the original was written in, or the sentence says «Позвоните Руслан
    Хвостов» and the model repairs the disagreement. A repaired token does not
    match the vault, and then the customer's tool executes on a person who does
    not exist — silently, which is the worst way for this to fail.

    Only NAME is inflected. Numbers and documents have no case, and LOC is
    generated as a whole phrase whose internal agreement is the generator's job.
    """
    if isinstance(span, PartSpan):
        # ONE substitute for the record, this leaf's part of it, in the leaf's
        # own form — lower case where the record wrote lower case, no type
        # word where it wrote none. A role the substitute cannot show (it
        # mirrors the whole's shape, so this is a defence, not a path) gets
        # the whole substitute rather than the real part.
        #
        # THE SPLITTER IS CHOSEN BY TYPE, because a composite object is not only
        # an address: `morph_places.split_roles` reads a street out of a phrase,
        # and `{"passport": {"series", "number"}}` is split by the DIGIT LENGTH
        # the leased map declares for each role. Both go through the same rule —
        # the record is ONE value, the leaf shows ITS part.
        if span.entity_type != "LOC":
            return _document_part(span, vault)
        whole = vault.tokenize(span.whole, "LOC")
        part = morph_places.split_roles(whole).get(span.role, "")
        if not part:
            # A CITY LEAF THE SUBSTITUTE CANNOT SHOW STAYS AS WRITTEN — a
            # settlement alone is not personal data (the same line the bare
            # city and `_settlement_of` draw), and the whole token in a field
            # called «city» told the model the record was another address
            # (live v4, chain-009). Any other missing role still gets the
            # whole substitute: fail closed on the street and the house.
            return span.value if span.role == "city" else whole
        if span.role == "street":
            # THE FAKE STREET IN THE CUSTOMER'S FORM — his type word or none.
            # The substitute is minted WITH a type («улица Мятная»); a record
            # field that held a bare «луговая» must mask to a bare «мятная»,
            # or we inject an «улица» the customer never wrote — the same
            # «type word is content» rule the restore leg applies, mirrored.
            # `_street_like` keeps the fake's NAME, takes the type-presence and
            # the letter-case from the customer's field.
            return morph_places._street_like(part, span.value)
        part = morph_places.part_in_form_of(span.value, part, span.role)
        if span.value.islower():
            return part.lower()
        if span.value.isupper():
            return part.upper()
        return part
    token = tokenize_span(span, vault)
    if span.entity_type in {"PHONE", "SNILS", "INN", "CARD", "PASSPORT", "DOB", "DATE", "EMAIL", "PLATE",
                            # the v6 checksum family: the substitute is shown in
                            # the customer's own separators/case, the same mirror
                            # the restore leg re-applies in the agent's.
                            "IMEI", "ICCID", "EPTS", "UIN", "LOYALTY",
                            "IBAN", "LOAN_UID", "VIN",
                            # …AND THE EIGHT RECORDS WHOSE SPAN NOW CARRIES THE
                            # REGISTRY ID (G7). The vault translates the label
                            # back, but this branch runs on the SPAN, before
                            # `tokenize_span`, so both spellings have to stand
                            # here or a masked ОМС/ПТС/счёт would reach the model
                            # in the vault's fallback rendering instead of the
                            # customer's own notation.
                            "OMS_ENP", "BANK_ACCOUNT", "OGRNIP", "EPTS_NUMBER",
                            "LOYALTY_CARD_NUMBER",
                            # the v6 identity documents: a certificate's roman
                            # series, a ПТС's letters and every document's
                            # separators are the customer's, on both legs.
                            "INTL_PASSPORT", "BIRTH_CERT", "CIVIL_ACT_CERT",
                            "MILITARY_ID",
                            "DRIVER_LICENSE", "RESIDENCE_PERMIT", "VEHICLE_DOC",
                            "PTS_NUMBER", "STS_NUMBER",
                            # the v6 legal family: a case number's separators and
                            # its Cyrillic/Latin twins, a writ's blank series and
                            # a cadastral number's colons are the sender's form.
                            *ru_pii_v6.LEGAL_LABELS,
                            # the v6 finance family: a policy's series letters,
                            # a claim's «У-» prefix and every document's
                            # separators are the sender's form on both legs.
                            *ru_pii_v6.FINANCE_LABELS,
                            # the v6 telecom/device family: a MAC's colons, a
                            # UUID's hyphens and letter case, and an IPv6
                            # address's group count are the writer's on both legs
                            # — the content (the hex digits, the octets) is the
                            # vault's.
                            *ru_pii_v6.TELECOM_FAMILY_LABELS,
                            # the v6 utility/account/education/travel family,
                            # same rule: a ЕЛС's series, a login's handle and
                            # every document's separators are the writer's on
                            # both legs — the content is the vault's.
                            *ru_pii_v6.UTILITY_LABELS}:
        # The vault reuses content, not the presentation of its first mention.
        # A tool result may write +7 after the user wrote 8 (or vice versa).
        #
        # A FAMILY THAT LAYS ITS OWN LAYOUT IS NOT MIRRORED A SECOND TIME. The
        # vault already decided this at the mint: `telecom_own_layout` is True for
        # an IPv4 address (a whole reserved address, not a run of the source's
        # length) and for the IPv4-MAPPED IPv6 form, and the token was stored in
        # the family's own notation. Mirroring it again into the source's
        # separators is where the mapped form broke: source «::ffff:192.168.1.1»
        # and fake «::ffff:198.18.8.71» carry the same twelve alphanumeric
        # characters with their dots in different places, so the second mirror
        # produced «::ffff:198.188.7.1» — a valid address shape that is NOT the
        # token, i.e. a FAKE the restorer cannot see (measured: 1 in 60 mints;
        # found by this family's witness, and it is a cross-family defect of the
        # seam rather than of one type).
        if (span.entity_type in ru_pii_v6.TELECOM_FAMILY_LABELS
                and ru_pii_v6.telecom_own_layout(span.entity_type, span.value)):
            return token
        return _atomic_in_form_of(span.value, token, span.entity_type)
    if span.entity_type == "LOC":
        # Same reason as NAME: a nominative phrase dropped into an oblique slot
        # reads as broken Russian, and broken Russian is what makes a model
        # rewrite the token instead of using it.
        case = morph_places.street_case(span.value)
        if case is None or case == "nomn":
            # THE FORM IS THE CUSTOMER'S ON THE WAY IN. `in_form_of` lays the
            # fake into the customer's own surface — lower case where he wrote
            # lower case, «д69» glued where he glued it, no comma where he
            # wrote none, his type word or none — the mirror of laying the real
            # value into the agent's form on the way out. Shown a clean,
            # capitalised, spaced fake, a rewriting model has nothing to
            # normalise and copies it, so the tool receives the customer's raw
            # string, never the model's own form; shown the customer's messy
            # form, the model reformats it exactly as it would the real value,
            # and the real value comes back in THAT form. This is the base
            # positioning — we make the same presentation the customer did.
            # Measured on the public rewriter agent (26 of 39 address
            # round-trips). Oblique mentions keep the grammatical inflection
            # below, prose reads on their agreement.
            #
            # FAIL-SAFE: the mirror must preserve the FAKE's identity. A
            # numbered or two-word street («4-й Вешняковский», «Ольгина пруда»)
            # can mis-align in `in_form_of` and leave the customer's real word
            # or number standing — «черёмуховаяд 5-й Вешняковский», the real
            # «Вешняковский» to the model. So the mirror is accepted only when
            # NO REAL WORD AND NO REAL DIGIT SURVIVES IN IT
            # (`_mirror_leaks_nothing`); otherwise the safe canonical fake is
            # shown. Correctness over form: we never leak a real part to gain
            # the customer's presentation.
            agreed = _agree_settlement(token, span.value)
            shown = morph_places.in_form_of(agreed, span.value)
            if shown and _mirror_leaks_nothing(shown, agreed):
                return shown
            return agreed
        # КОСВЕННЫЙ ПАДЕЖ ПОЛУЧАЕТ СКЛОНЁННУЮ ФРАЗУ ЦЕЛИКОМ, А НЕ ГОЛОЕ
        # НАЗВАНИЕ. Зеркало отправителя («Встретимся на Тверской 7» → «…на
        # Луговой 2») оставляло подмену БЕЗ родового слова, и `detect_case`
        # читает голое «Луговой» как именительный — то есть подмена в косвенном
        # слоте, ровно то, от чего этот путь и заведён (test_hard_cases). Форма
        # при этом не наша: падеж, число и маркер берутся у отправителя, а
        # родовое слово — из записи (см. `_compose_head`: голова, пришедшая от
        # ДРУГОГО упоминания, пересобирается в форме этого, поэтому чужое «ул.»
        # сюда не просачивается).
        return morph_places.inflect_place(token, case)
    if span.entity_type != "NAME":
        return token
    # ONE reading for the key, the gender and the case (`read_person`): the
    # token was minted for this gender, and it is bent into the case the
    # sentence — not a vote over the words — says the person stands in.
    gender, case = morph_names.read_person(
        span.value, span.cases if isinstance(span, NameSpan) else ())
    # …IN THE WORD ORDER OF THIS MENTION. One person is one token, minted in
    # the arrangement of the FIRST mention («рушан есин» → «Гордей Якушев»);
    # the customer then writes «есина рушана», and a token shown given-first
    # in a surname-first sentence is a form the customer never wrote — the
    # agent copies it, and the tool receives the name reordered. The parts
    # are permuted by role when the two shapes are the same set of roles.
    token = _parts_in_order_of(token, span.value)
    if case is not None and case != "nomn":
        token = morph_names.inflect_person(token, case, gender)
    # …AND INTO THE LETTER CASE THE CUSTOMER WROTE. «игорь анфалов» used to
    # become «Максим Дмитров»: the substitute changed the form before the
    # agent ever saw it, so an agent that copies verbatim copied OUR
    # capitals, and the tool received «Игорь Анфалов» for a customer who
    # never wrote a capital — measured on the public benchmark, where every
    # chat-register name came back re-cased. The address leaves already
    # mirror the record's case (above); a name mirrors the sentence's. The
    # form belongs to the customer on the way in and to the agent on the way
    # out; ours appears nowhere.
    return agent_form.name_cased_like(token, span.value)


def _parts_in_order_of(token: str, mention: str) -> str:
    """The token's words permuted into the role order of `mention`, when both
    read as the same set of roles in a different order; the token itself
    otherwise (a shape the reader cannot pair is left alone rather than
    guessed at)."""
    ours = morph_names.name_shape(token)
    theirs = morph_names.name_shape(mention)
    words = token.split()
    if len(ours) != len(words) or len(theirs) != len(words) or ours == theirs:
        return token
    if sorted(ours) != sorted(theirs) or len(set(ours)) != len(ours):
        return token
    by_role = dict(zip(ours, words))
    return " ".join(by_role[role] for role in theirs)


# ОДНА БУКВА ИЛИ ОДНА ЦИФРА ЗНАЧЕНИЯ — то, из чего складывается «дословно».
# `\w` без подчёркивания: подчёркивание разделяет слова в поле схемы, а не
# внутри значения.
_VALUE_RUN = re.compile(r"[^\W_]+", re.UNICODE)
# Буквенный прогон и цифровой прогон ПОРОЗНЬ — ими значение опознаётся.
# «д36» — один прогон значения, но слово в нём «д», а число «36».
_LETTER_RUN = re.compile(r"[^\W\d_]+", re.UNICODE)


class _AsWritten(NamedTuple):
    """ONE value this dialogue was shown, and how the customer spelt each of its
    words. `words` and `digits` are what IDENTIFY the value; `spellings` is what
    it has to say about a rebuild of itself."""

    words: frozenset[str]
    digits: frozenset[str]
    offers: bool
    spellings: dict[str, str]


def _significant_words(text: str) -> frozenset[str]:
    """The words that NAME this value rather than its slots. A generic street
    word («улица», «дом», «кв»), a settlement marker and a one- or two-letter
    abbreviation say which FIELD a piece is, not which place it is — and the
    rebuild adds and drops them freely, so a value would never recognise itself
    across them."""
    return frozenset(
        word for word in (_fold_word(run.group()) for run in _LETTER_RUN.finditer(text))
        if len(word) > 2 and word not in _SETTLEMENT_MARKERS
        and not morph_places.is_generic_word(word))


def _conflict_key(entity_type: str, value: str) -> str:
    """The TYPED identity the vault itself keys this value under.

    `fold_key` after `canonicalize` for a NAME, the same pair `remember_shown`
    compares two owners with: a person is neither a capitalisation nor a
    diaeresis, so a dialogue that could not decide between two people cannot
    decide between two spellings of one of their surfaces either. Every other
    type keeps its own canonical form — the digits of a СНИЛС, the `+7…` of a
    phone, the upper-cased ГОСТ alphabet of a plate, the address key of a place
    — because those ARE the identity, and inventing a second one here would let
    this test and the vault disagree about what "the same value" means.
    """
    canonical: str = canonicalize(entity_type, value)
    return fold_key(canonical) if entity_type == "NAME" else canonical


def _conflict_keys(shown_forms: list[tuple[str, str, str]]) -> dict[str, frozenset[str]]:
    """The identities THIS dialogue recorded as unresolved, grouped by type.

    `Vault.remember_shown` writes a self-mapping (`shown == original`) when two
    owners claim one surface, so the marker is read exactly as it is written
    there. Grouped by type because `canonicalize` is typed: one call per type
    that actually conflicted, and NOTHING AT ALL in the ordinary dialogue that
    has none — the cost is proportional to the doubt, not to the answer.
    """
    keys: dict[str, set[str]] = {}
    for shown, original, kind in shown_forms:
        if not shown or shown != original:
            continue
        key: str = _conflict_key(kind, shown)
        if key:
            keys.setdefault(kind, set()).add(key)
    return {kind: frozenset(values) for kind, values in keys.items()}


def _conflicts_with(surface: str, conflicts: dict[str, frozenset[str]]) -> bool:
    """This surface IS an identity the dialogue could not resolve.

    Asked of a whole surface, never of a piece of one: a larger projection
    whose own identity is unambiguous — a full address containing a contested
    house — still names one owner and is left to the restoring leg.
    """
    if not conflicts:
        return False
    return any(_conflict_key(kind, surface) in keys
               for kind, keys in conflicts.items())


def _as_written_rows(shown_forms: list[tuple[str, str, str]]) -> tuple[_AsWritten, ...]:
    """The spelling THIS DIALOGUE used, kept PER VALUE it was written in.

    THE CONTENT THAT LEAVES IS WHAT THE CUSTOMER WROTE (D-067). Detection reads
    the NORMALISED text, so the vault holds «васи алексеева 36» where the
    customer typed «ваcи алексеева 36» with a Latin «c», and every leg that
    rebuilds a form — `in_form_of`, `part_in_form_of`, the digit splice, the
    name caser — rebuilds it out of the folded canon. An agent that COPIED the
    substitute already gets the literal back (`_restore_verbatim_spans`); an
    agent that REWROTE it got the customer's slip silently repaired, which is
    the gateway deciding for the customer's own system — and we do not correct
    what the customer wrote, in either direction. Correcting the address is the
    AGENT's business, exactly as `_pick_value` already says about a typo.

    A SLIP BELONGS TO THE VALUE IT WAS WRITTEN IN, NOT TO THE WORD. Keyed by
    the word across the whole dialogue, a Latin «a» in «гагаринa 12» — the
    street — was laid into «Гагарина Петра Ильича», the PERSON, on the way back
    to the tool: one message, two values, one shared word, and the customer's
    CRM got a surname with a Latin letter in it that nobody ever typed. The
    same keying also refused both values their own spelling whenever two of
    them wrote one word differently, because a single table cannot hold two
    answers. So a row is one value — one span occurrence, the unit
    `remember_shown` already records — and it speaks only about a rebuild of
    ITSELF.

    HOW A VALUE RECOGNISES ITS OWN REBUILD: every significant word of the
    rebuild is a word of the value, and the digits do not contradict. The
    rebuild adds and drops the words that name slots («улица», «д.», «кв.»)
    and it re-cases freely, so those cannot be part of the test
    (`_significant_words`); the NAME of the street and of the person cannot be,
    so they are.

    CONTAINMENT, NOT EQUALITY, AND IN THAT DIRECTION. A rebuild is often a PART
    of the value: the settlement is real in the substitute already, so the span
    the restorer replaces is «Серебрянический 87 кв 147» while the customer
    wrote «оренбург серебряничeский 87 кв 147», and a schema asking for
    `street` alone gets one word of it. Equality refused both and took the slip
    back off two of the public benchmark's addresses. The other direction is
    what must NOT be allowed: a rebuild carrying words the value does not have
    is a DIFFERENT value that merely shares one — «Гагарина Петра Ильича», the
    person, against «гагаринa 12», the street.

    THE DIGITS TELL TWO MENTIONS OF ONE STREET APART — «садовaя 5 кв 10» and
    «садовая 7 кв 12» share every word and are different addresses — and they
    are compared by containment too, because a schema that asks for no flat
    drops one honestly and a `street` field carries none at all.

    WHY A TABLE OF WORDS AND NOT THE WHOLE VALUE. The literal cannot simply
    replace the canon as the CONTENT of the rebuild: the rebuilders read the
    value with morphology (`split_roles`, `to_nominative`, the date reader,
    `digits_of`), and a Latin letter inside a Cyrillic word — or a letter
    standing where a digit belongs — is exactly what those readers cannot
    parse. So the canon does the work and the OUTPUT is re-spelled, word by
    word, at the end. `normalize` is 1:1 and length-preserving, which is what
    makes the two spellings line up by offset and what lets the re-spelling be
    a character-for-character swap rather than a guess.

    AMBIGUITY IS REFUSED, NOT RESOLVED. A word this dialogue wrote two ways
    INSIDE THE SAME VALUE — or two recorded mentions of one value that disagree
    — has no single «as written», and the canon is then the honest answer. A
    dialogue with no recorded slice at all (a token minted in another
    conversation, a volume written before `shown_forms` existed) recognises
    nothing and gets the canon, for the same reason: there is nothing else to
    return.

    A NAME OFFERS NO SPELLING, AND THE LINE IS `_pick_value`'S OWN. That
    function already decides what a value IS on the way out: for a NAME the
    CANONICAL nominative, because a declined name is not what belongs in a
    customer's CRM field, and for every other type the customer's own string.
    Re-spelling is that same rule carried down to the character, so it reaches
    exactly the values that are the customer's writing and leaves the one whose
    outward form is ours by an older decision. Measured, not reasoned: on the
    public benchmark's rewriting agent, restoring the slip inside a NAME moved
    13 values from delivered to «repaired» (−6.4 pp on the NAME line) while the
    address line gained 11.8 pp, because that instrument's model of an agent
    folds a look-alike in a person's name and keeps it in a street's.
    THE PREMISE THAT WOULD SETTLE IT IS NOT BUILT YET: D-067 rests on the
    substitute carrying the SAME slip, so that an agent which folds the fake's
    letter tells us it would have folded the customer's — the mint does not
    mirror the slip today, so there is nothing to read the agent's intent from.
    A NAME row is still KEPT, and still says how the dialogue spelt its own
    words: a person and a street written identically are one value to every
    test here, and the name's clean spelling is then what refuses the street's
    slip.

    THE RESIDUAL RISK, STATED: a rebuild that is ONE WORD and no digits — a
    lone `street` or `last_name` field — is contained in every value of the
    dialogue that holds that word, so a person named exactly as a street is
    spelt cannot be told from the street. Both are then answered together, and
    they agree unless the dialogue wrote them differently — in which case they
    disagree and the canon wins, which is the outcome that matters. Separating
    them needs the span's TYPE carried down to the splice, which the restoring
    legs do not return today.
    """
    if not shown_forms or not ASSETS.is_loaded:
        return ()
    rows: list[_AsWritten] = []
    for _shown, literal, kind in shown_forms:
        # A CONFLICT MARKER IS NOT A WRITING. `remember_shown` records «we could
        # not decide between two owners» by writing the SHOWN string into
        # `original`; read as a spelling that row would teach the restorer that
        # the customer wrote the real value with the SUBSTITUTE's letters — a
        # rebuilt name or street would come back wearing a look-alike the
        # customer never typed. The marker is evidence about identity only.
        if _shown == literal:
            continue
        folded = normalize(literal)
        if len(folded) != len(literal):
            continue
        spellings: dict[str, str] = {}
        refused: set[str] = set()
        for run in _VALUE_RUN.finditer(literal):
            canonical = folded[run.start():run.end()]
            if _VALUE_RUN.fullmatch(canonical) is None:
                continue
            key, written = canonical.lower(), run.group().lower()
            if spellings.setdefault(key, written) != written:
                refused.add(key)
        rows.append(_AsWritten(
            words=_significant_words(folded),
            digits=frozenset(run.group() for run in _DIGIT_RUN.finditer(folded)),
            offers=kind != "NAME",
            spellings={key: written for key, written in spellings.items()
                       if key not in refused}))
    return tuple(rows)


def _spellings_for(value: str, rows: tuple[_AsWritten, ...]) -> dict[str, str]:
    """What the customer's own writing of THIS value was, as far as the rows
    that are this value agree on it. A word no non-NAME row offers keeps the
    canon (see `_as_written_rows`); a word two matching rows spell differently
    keeps it too."""
    if not rows:
        return {}
    words, digits = _significant_words(value), frozenset(
        run.group() for run in _DIGIT_RUN.finditer(value))
    mine = [row for row in rows if words <= row.words
            and (row.digits <= digits or digits <= row.digits)]
    if not mine:
        return {}
    table: dict[str, str] = {}
    refused: set[str] = set()
    offered: set[str] = set()
    for row in mine:
        for key, written in row.spellings.items():
            if table.setdefault(key, written) != written:
                refused.add(key)
            if row.offers:
                offered.add(key)
    return {key: written for key, written in table.items()
            if key in offered and key not in refused and written != key}


def _as_written(text: str, table: dict[str, str]) -> str:
    """A rebuilt value re-spelled the way the customer wrote it, with the
    AGENT'S letter case kept (Б24: content from the customer, form from the
    agent). Only whole runs are touched and only when the lengths agree, so
    the swap is one character for one character and nothing is inserted or
    dropped."""
    if not table:
        return text
    pieces: list[str] = []
    last = 0
    for run in _VALUE_RUN.finditer(text):
        word = run.group()
        written = table.get(word.lower())
        if written is None or len(written) != len(word):
            continue
        pieces.append(text[last:run.start()])
        pieces.append("".join(spelt.upper() if shown.isupper() else spelt
                              for spelt, shown in zip(written, word)))
        last = run.end()
    if not pieces:
        return text
    pieces.append(text[last:])
    return "".join(pieces)


class _Literals(NamedTuple):
    """What this dialogue was shown, the customer's own spelling of every
    word the fold rewrote, VALUE BY VALUE, and the identities the dialogue
    could not resolve. READ ONCE PER DETOKENISATION, not
    per JSON leaf: `unmask_arguments` calls the restorer for every string in
    the object, and rebuilding the rows there made a fifteen-field tool call
    pay for it fifteen times (+16% measured, 65 → 75 ms)."""

    forms: list[tuple[str, str, str]]
    as_written: tuple[_AsWritten, ...]
    conflicts: dict[str, frozenset[str]]


def _literals_of(vault: Vault) -> _Literals:
    forms = vault.shown_forms()
    return _Literals(forms, _as_written_rows(forms), _conflict_keys(forms))


def _call_texts(raw: str) -> tuple[str, ...]:
    """Из чего состоит ОДИН вызов: сам текст и каждый его строковый лист.

    ОДНО ОПРЕДЕЛЕНИЕ НА ВСЕ ТРИ ВХОДА (`unmask_text`, `unmask_arguments`,
    `surviving_substitutes`), потому что восстановление и сигнал обязаны
    считать вызовом одно и то же: разойдясь, они однажды доложили бы об отказе,
    которого не было, или промолчали бы о состоявшемся. Лист нужен отдельно от
    целого — поле, состоящее ИЗ ОДНОГО числа, узнаётся только как лист
    (`_WHOLE_NUMBER`), а «123456» посреди JSON не узнаётся никак; проза своим
    единственным листом является сама (`_string_leaves`)."""
    return (raw, *(value for _key, value in _string_leaves(raw)))


def _written_digits(texts: tuple[str, ...]) -> tuple[str, ...]:
    """Числа, написанные агентом в этом вызове, — и ровно те, которые
    восстановление считает ЗНАЧЕНИЯМИ, а не количествами.

    Извлекаются теми же тремя правилами, которыми восстановление решает, что
    перед ним значение: длинный прогон (`_NUM_RUN`), поле целиком из числа
    (`_WHOLE_NUMBER`) и число под подсказкой (`_CUE_NUMBER`). Брать все группы
    цифр подряд было бы неверно: «+7 939 222-76-19» распалось бы на пять чисел,
    и одно из них совпало бы с количеством заказчика само собой — то есть
    якорь подтверждал бы сам себя. Что с ними делает волт — `_tiling`."""
    runs: set[str] = set()
    for text in texts:
        stripped = text.strip()
        for match in _NUM_RUN.finditer(text):
            runs.add(re.sub(r"\D", "", match.group()))
        if stripped and _WHOLE_NUMBER.fullmatch(stripped):
            runs.add(re.sub(r"\D", "", stripped))
        for match in _CUE_NUMBER.finditer(text):
            runs.add(re.sub(r"\D", "", match.group("num")))
    return tuple(sorted(run for run in runs if run))


def _call_view(texts: tuple[str, ...], vault: Vault) -> Vault:
    """Вид волта, знающий, КАКИЕ ЧИСЛА агент написал в этом вызове — якорь, по
    которому кусок пришивается к целой подмене за пределами разговора
    (`Vault.with_written_digits`).

    СЧИТАЕТСЯ РАЗ НА ВЫЗОВ, А НЕ НА ЛИСТ. `unmask_arguments` зовёт
    восстановление для каждой строки объекта, и вопрос, заданный внутри, стоил
    бы вызову с пятнадцатью полями пятнадцать запросов вместо одного — та же
    цена, из-за которой раз на вызов читаются и `shown_forms`. Здесь это не
    только цена: соседнее поле того же вызова — это ровно то, о чём вопрос, и
    лист, разобранный в одиночку, ответа на него не содержит.
    """
    return vault.with_written_digits(_written_digits(texts))


def _argument_view(texts: tuple[str, ...], vault: Vault) -> Vault:
    """Тот же вид ПЛЮС вето: какие подмены агент написал в этом вызове целиком
    (Б29, `Vault.with_spent_signatures`).

    ВЕТО ЖИВЁТ НА ПЛЕЧЕ АРГУМЕНТА, И ТОЛЬКО НА НЁМ. Оно закрывает случай
    «собственное число заказчика стоит рядом с подменой, написанной целиком», а
    случай этот бывает там, где голое число — само по себе поле схемы: в
    аргументе `_restore_reformatted_spans` читает лист, состоящий из одних
    цифр, БЕЗ единого слова о том, чей он. В ПРОЗЕ такого входа нет — короткое
    число трогается только под подсказкой, которая сама называет его нашим
    («последние четыре цифры», «серия», «контрольное число»), то есть защищать
    вето там нечего. Зато цена его там была прямая и ежедневная: «Телефон
    +7 916 402-11-87 — последние четыре цифры 1187» уходил заказчику двумя
    разными номерами в одной фразе, молча.

    И ЭТО ЖЕ СВОДИТ ОБРАТНО ДВА ПЛЕЧА ОДНОГО ОТВЕТА. `unmask_stream_chunk`
    зовёт `unmask_text` на каждый отдаваемый кусок, поэтому «весь вызов» на
    потоке — это то, что успело выйти из carry, а в буфере — весь текст. Пока
    вето читало прозу, один и тот же ответ модели приходил к заказчику с разным
    хвостом в зависимости от того, буферизован он или нет; расхождение половин
    продукта дороже любого выигрыша, за который его покупают.

    Кандидатов в целые подмены предлагает ФОРМА, а нашими их называет ВОЛТ —
    тот же порядок, что у восстановления целой подмены. Форм две, и обе
    обязательны: `token_re` знает чеканенные написания, но телефон ловит только
    слитным (`+79…`), а агент пишет его группами и через 8 — цифровой прогон
    (`_NUM_RUN`) и есть та форма, которой целую переформатированную подмену
    находит `_restore_reformatted_spans`.
    """
    anchored = _call_view(texts, vault)
    written = frozenset(
        match.group()
        for text in texts
        for pattern in (token_re(), _NUM_RUN)
        for match in pattern.finditer(text))
    if not written:
        return anchored
    return anchored.with_spent_signatures(anchored.whole_substitute_signatures(written))


def unmask_text(text: str, vault: Vault, inflect: bool = True,
                for_tool: bool = False, target: str = "",
                restoration: RestorationField | None = None) -> str:
    """Replace tokens with their real values, then catch numeric tokens the model
    REFORMATTED via a digit-signature match.

    Candidates are found by SHAPE (`Vault.TOKEN_RE`) and resolved in batched
    indexed lookups, so the cost tracks the length of the answer rather than the
    size of the vault. The previous approach loaded every token the org had ever
    minted and substring-scanned the text once per token, which made an org with
    100k tokens pay 100k scans on every single response.

    `target` — the leaf's schema-declared notation (класс Ж), or "" when the
    schema declares none; never guessed.
    """
    literals = _literals_of(vault)
    restored = _unmask(text, _call_view(_call_texts(text), vault), literals,
                       inflect, for_tool, target=target, restoration=restoration)
    if not for_tool:
        joined = _join_addresses_in_json_value(restored, text, vault, literals, restoration)
        if joined is not None:
            if restoration is not None:
                restoration.json(text, joined, include_splices=True)
            return joined
    return restored


# РОЛЬ ЧИТАЕТСЯ ИЗ ИМЕНИ ПОЛЯ И НА КОНТЕНТ-ПЛЕЧЕ (W1). Плечо аргумента собирает
# адрес, разложенный по полям схемы (`_join_addresses_deep`), а прозаическое плечо
# знает только текст: ключ `"build"` для него — просто слово, и голая «44» без
# подсказки рядом владельца не находит. Поэтому ответ, который ЦЕЛИКОМ является
# JSON-объектом схемы, разбирается тем же соединением. Узко: только объект
# целиком, только когда в нём есть адресная роль и хотя бы один её лист остался
# НЕразрешённым (`restored == original` — ровно то условие, по которому соединение
# и переписывает лист). Всё остальное уходит прежней дорогой, без пересборки JSON.
def _join_addresses_in_json_value(restored: str, original: str, vault: Vault,
                                  literals: _Literals,
                                  restoration: RestorationField | None = None) -> str | None:
    stripped = original.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None
    try:
        restored_obj = json.loads(restored)
        original_obj = json.loads(original)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(restored_obj, dict) or not isinstance(original_obj, dict):
        return None
    roles = {key: morph_places.role_of_field(str(key)) for key in original_obj}
    if not any(roles.values()):
        return None
    if not any(roles.get(key) and restored_obj.get(key) == value
               for key, value in original_obj.items() if isinstance(value, str)):
        return None
    joined = _join_addresses_deep(restored_obj, original_obj, vault, literals, restoration)
    if joined == restored_obj:
        return None
    return json.dumps(joined, ensure_ascii=False)


def _address_clauses(text: str) -> list[tuple[int, int]]:
    """Куски между границами предложений, в которых есть АДРЕСНАЯ ПОДСКАЗКА.

    ЗАЧЕМ ЭТО ВТОРОЙ ВИД ОКНА. `_PLACE_RUN` ищет адрес по РОДОВОМУ слову, а
    подмена зеркалит отправителя: клиент, написавший «казань зацепская 7 кв 31»
    без типа, видит свою подмену тоже без типа («казань речная 4 кв 229»).
    Скрестив её с чужим номером — «г казань, речной, д 4, кв 78», — получаем
    текст, в котором родового слова нет вовсе: прогон его не находит,
    противоречие не замечается, и каждая часть разрешается СВОИМ владельцем —
    настоящий дом одного адреса и настоящая квартира другого
    (test_location_form_adversarial F/two). Клауза с адресной подсказкой —
    минимальное окно, которое ещё видит целое.
    """
    out: list[tuple[int, int]] = []
    for match in re.finditer(r"[^;\n]+", text):
        piece = match.group()
        # КЛАУЗА С РОДОВЫМ СЛОВОМ УЖЕ ЕСТЬ У ПРОГОНА — второй раз её спрашивать
        # нечем, и вредно: роль улицы у такого окна начинается с ПРОЗЫ («Офис на
        # Вязовом проспекте»), её лист не находит владельца вовсе, и один
        # найденный корпус уже даёт «двух владельцев» — окно объявлялось
        # противоречивым и блокировало верный адрес (test_hard_cases: «Офис на
        # Ленинском проспекте, дом 10, корпус 3» не возвращался).
        # СЛОВО, А НЕ СТРОКА: `_STREET_TYPE_WORD` якорный, и им проверяется один
        # токен, а не вся клауза.
        if any(_STREET_TYPE_WORD.match(word.strip(" .,"))
               for word in re.findall(r"[А-Яа-яЁё.-]+", piece)):
            continue
        if re.search(r"(?i)\b(?:дом|д|кв|квартир\w*|корп\w*|стр|под[ъь]езд\w*)\.?\s*\d", piece):
            out.append((match.start(), match.end()))
    return out


def _conflicting_place_spans(text: str, vault: Vault,
                             exact: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Keep contradictory address mentions unresolved, not partly real.

    Schema fields already require their known parts to name one owner. A
    prose or JSON-string address carries the same evidence in its markers.
    Exact whole mentions have stronger evidence than independently found
    numeric fragments and retain their existing restoration path.
    """
    windows: set[tuple[int, int]] = {
        framing
        for match in _PLACE_RUN_ANY_CASE.finditer(text)
        for framing in _place_windows(text, match.start(), match.end())}
    windows.update(_address_clauses(text))
    blocked: list[tuple[int, int, str]] = []
    for start, end in sorted(windows, key=lambda pair: pair[1] - pair[0], reverse=True):
        if any(low <= start and end <= high for low, high, _ in exact + blocked):
            continue
        surface: str = text[start:end]
        roles: dict[str, str] = morph_places.split_roles(surface)
        if len(_role_owners(roles, vault)) > 1:
            blocked.append((start, end, surface))
    return blocked


def _unmask(text: str, vault: Vault, literals: _Literals, inflect: bool,
            for_tool: bool, field_key: str = "", target: str = "",
            restoration: RestorationField | None = None) -> str:
    with stage("unmask.total"):
        # EVERY PASS READS THE SAME MASKED TEXT, AND THE EXACT TOKENS WIN. The
        # passes used to run one after another on the text the previous pass
        # had restored, so the name windows ran over REAL values already put
        # back — and a real «Иван» that happened to equal another customer's
        # substitute «Иван» was resolved a second time into that other
        # person («Иван Петров» → «валерий Петров», hard cases, one vault).
        # A restored range is closed to every later pass.
        # COPIED VERBATIM COMES BACK VERBATIM. Before any form is rebuilt, every
        # occurrence of a form this dialogue was SHOWN is put back as the
        # customer's literal string — the typo, the look-alike letter, the
        # address with no street word, all of it: exactly what an agent that
        # copies would have passed without us. Form is rebuilt only for text
        # the agent changed, by the passes below.
        # ONE READ OF THE DIALOGUE'S LITERAL SLICES, TWO USES: the verbatim
        # pass puts a COPIED substitute back as the customer's whole string,
        # and the table re-spells what the other passes REBUILD.
        resolved_spans = _restore_inflected_candidates(text, vault, inflect, for_tool)
        inflected_spans: list[tuple[int, int, str]] = [
            (span.start, span.end, span.value) for span in resolved_spans]
        verbatim_spans = _restore_verbatim_spans(text, literals.forms, for_tool)
        token_spans = _restore_tokens_spans(text, vault, for_tool, target=target)
        # THE TWO PASSES ABOVE RESOLVE A SUBSTITUTE BY ITS STRING, WITH NO
        # EVIDENCE ABOUT WHAT IT STOOD FOR. That is sound for a long, distinctive
        # substitute and NOT for the temporary-secret classes, whose card code has
        # a domain of a thousand values: an unrelated three-digit number equal to
        # a shown substitute would come back as the customer's real code, silently,
        # in a tool call. Dropped only where the class is not named — every other
        # type's span is returned untouched (`cvc.drop_uncontexted`).
        verbatim_spans = cvc.drop_uncontexted(text, verbatim_spans, vault, for_tool,
                                              field_key)
        token_spans = cvc.drop_uncontexted(text, token_spans, vault, for_tool,
                                           field_key)
        # A resolved composite address owns its entire range. Restoring a
        # copied house/flat first would prevent the overlapping street+house
        # projection from being applied, creating a real/fake hybrid.
        taken: list[tuple[int, int, str]] = _conflicting_place_spans(
            text, vault, verbatim_spans + token_spans)
        for candidate in sorted(resolved_spans, key=lambda item: item.end - item.start, reverse=True):
            start, end, value = candidate.start, candidate.end, candidate.value
            entity_type = candidate.entity_type
            surface: str = text[start:end]
            if entity_type in {"LOC", "ADDR"}:
                roles: dict[str, tuple[int, int]] = morph_places.role_spans(surface)
                if "street" not in roles or "house" not in roles:
                    continue
            elif entity_type == "NAME":
                # A complete aligned/lookup-bound name is stronger than an
                # unrelated shorter token inside it (legacy cross-script mint
                # collisions). Inferred residual fragments do NOT get this
                # priority: length alone cannot prove they share one identity.
                if not candidate.bound_identity or len(surface.split()) < 2:
                    continue
            else:
                continue
            # A copied whole has exact spelling evidence, including typos.
            # Only smaller copied leaves must yield to their resolved whole.
            if any(low <= start and end <= high for low, high, _ in verbatim_spans + token_spans):
                continue
            if not any(start < high and low < end for low, high, _ in taken):
                taken.append((start, end, value))
        for span in verbatim_spans:
            if not any(span[0] < end and start < span[1] for start, end, _ in taken):
                taken.append(span)
        for span in sorted(token_spans, key=lambda item: (item[0], -item[1])):
            if not any(span[0] < end and start < span[1] for start, end, _ in taken):
                taken.append(span)
        passes = [_restore_reformatted_spans(text, vault, for_tool, field_key, target=target),
                  _restore_spoken_identifier_spans(text, vault, for_tool)]
        # A cue inside a JSON string carries the same role as one in prose.
        # Field-level numeric values remain governed by the schema path.
        passes.append(_restore_cued_numbers_spans(text, vault, token_spans))
        # THE TEMPORARY SECRETS (C1, O-SECRET). Their substitutes are NOT in
        # `TOKEN_RE` on purpose: a bare `\b\d{3}\b` would make every three-digit
        # number of every answer a restoration candidate, and the class's domain
        # is 1000 values (`pseudex/cvc.py`, and the invariant it departs from
        # `vault.py:2278`). The pass asks the SAME evidence the masking leg asked
        # — the authoritative field name, or the bounded cue from the lease — so
        # a substitute resolves only where the class is named, and a candidate
        # that fails to resolve stays standing and is reported as a residual
        # (`surviving_substitutes` reads it off `shown_forms`), never emitted as
        # a fake.
        passes.append(cvc.restore_spans(text, vault, for_tool, field_key))
        passes.append(inflected_spans)
        for spans in passes:
            for span in sorted(spans, key=lambda item: (item[0], -item[1])):
                if not any(span[0] < end and start < span[1] for start, end, _ in taken):
                    taken.append(span)
        # CONTENT AS THE CUSTOMER WROTE IT, FORM AS THE AGENT WROTE IT. The
        # passes above rebuilt the form out of the normalised canon; the
        # re-spelling puts the customer's own characters back into it, and it
        # asks the VALUE that was rebuilt, not the dialogue — a slip belongs to
        # one value, and the span is the only place we still know which.
        # A verbatim span is already literal and its words carry the slip, so
        # it recognises no row and nothing changes — the pass is idempotent.
        # Refuse a conflicting identity only AFTER ranges have been selected:
        # skipping it earlier would let smaller parts restore another owner.
        # A larger unambiguous whole retains its normal precedence. Both OUT
        # consumers share this boundary, and no pass reads the restored output.
        rendered = [(start, end,
                     text[start:end] if _conflicts_with(text[start:end], literals.conflicts)
                     else _as_written(value, _spellings_for(value, literals.as_written)))
                    for start, end, value in taken]
        if restoration is not None:
            shift = 0
            for start, end, value in sorted(rendered):
                # Veto ranges reserve precedence but change nothing. Record only
                # the final rendered accepted splice, without another lookup.
                if value != text[start:end]:
                    restoration.splice(start, end, start + shift, start + shift + len(value))
                shift += len(value) - (end - start)
        return _splice(text, rendered)


# A SHORT NUMBER IN PROSE IS A QUANTITY — unless the word before it says what
# it is. «Верен ли номер дома 74?», «серия 45 09», «последние четыре цифры
# 4567», «контрольное число 59»: the model confirms a PIECE of the substitute
# with the customer, and the customer reads a house that is not theirs. The cue
# is the licence; without one nothing here fires, and the window is one
# adjacency, never a sentence.
#
# ОДНО СУЩЕСТВИТЕЛЬНОЕ МЕЖДУ ПОДСКАЗКОЙ И ЧИСЛОМ — И ТОЛЬКО ТО, ЧТО НАЗЫВАЕТ
# НАШ ТИП (Б29). «Серия паспорта 0025» и «номер паспорта 123456» — это то, как
# паспорт двумя полями звучит в ПРОЗЕ и в ПОТОКЕ, а окно требовало, чтобы
# подсказка КАСАЛАСЬ числа: одно слово между ними — и восстановление про этот
# кусок не спрашивало ВООБЩЕ, ни в одной области, включая названный разговор.
# Треть всей стороны «наше не вернулось» стояла на этом, и на потоке молча.
# РАСШИРЕНИЕ ОКНА — ЭТО ДВЕРЬ ДЛЯ НОВЫХ ЛОЖНЫХ ТРЕВОГ, поэтому внутрь пущен не
# «любой [а-яё]+», а перечень `_CUE_DOCUMENTS`: «номер счёта», «номер заказа»,
# «номер склада» — числа ЗАКАЗЧИКА, и они в окно по-прежнему не попадают.
# «Дома» в перечне нет намеренно: адрес разбирает ветка `_HOUSE_CUES`, и
# «номер дома» обязан остаться её словом, а не стать цифровым куском.
# СУЩЕСТВИТЕЛЬНОЕ ВНУТРИ ПОДСКАЗКИ — ЭТО СЛОВО ЦЕЛИКОМ, А НЕ ЕГО НАЧАЛО (Б29).
# Здесь стояло «карт\w*», «телефон\w*», и внутрь окна входили «номер картриджа»,
# «номер картотеки», «номер телефонограммы» — числа заказчика, которых мы
# никогда не подменяли: на базе эти фразы не трогались вовсе, а после
# расширения окна на их место МОЛЧА вставали цифры настоящей карты клиента.
# Поэтому перечислены ПАДЕЖНЫЕ ОКОНЧАНИЯ, а не «что угодно дальше»: у чужого
# корня после «карт» стоит «ридж», а «ридж» окончанием не бывает. Перечень —
# ровно наши четыре типа; «номер счёта», «номер заказа», «номер склада» в окно
# по-прежнему не попадают, потому что их в нём нет.
_CUE_DOCUMENTS = (
    ("PHONE", r"телефон(?:а|у|ом|е|ы|ов|ам|ами|ах)?"),
    ("CARD", r"карточк(?:а|и|е|у|ой|ам|ами|ах)?|карт(?:а|ы|е|у|ой|ою|ам|ами|ах)?"),
    ("SNILS", r"снилс(?:а|у|ом|е)?"),
    ("PASSPORT", r"паспорт(?:а|у|ом|е|ы|ов|ам|ами|ах)?"),
)
_CUE_DOCUMENT_RE = tuple(
    (kind, re.compile(rf"(?i)(?<![\wа-яё])(?:{pattern})(?![\wа-яё])"))
    for kind, pattern in _CUE_DOCUMENTS)
_CUE_DOCUMENT_ALT = "|".join(pattern for _kind, pattern in _CUE_DOCUMENTS)
_CUE_NUMBER = re.compile(
    r"(?i)(?<![\wа-яё])(?P<cue>(?:\*{4}\s?){2,3}|дом\w*|д\.|д(?=\s)|кв\.|кв(?=\s)|квартир\w*|подъезд\w*|корпус\w*|"
    r"(?:серия|серии|номер\w*)(?:\s+(?:" + _CUE_DOCUMENT_ALT + r"))?|"
    r"последн\w+\s+(?:[а-яё]+\s+){0,2}?цифр\w*(?:\s+[а-яё]+){0,2}|"
    r"контрольн\w+\s+числ\w*|заканчива\w+\s+на)\s*[:—–|-]?\s*(?:\*\*|`|«|\")?(?P<num>\d(?:[\d\s]{0,10}\d)?)(?![\d:])")
_HOUSE_CUES = ("дом", "д", "кв", "квартир", "подъезд", "корпус")
_SHORT_HOUSE_PREFIX = re.compile(r"(?i)(?:^|[,;:\n]|\b(?:к|у|в|из|до|от|около)\s+)\s*$")


def _licensed_number_cue(text: str, match: re.Match[str]) -> bool:
    """A bare house abbreviation needs a field boundary or address grammar.

    A letter followed by a number is also an initial or a category label.
    Finding that number in our vault does not turn the letter into a house.
    """
    return (match.group("cue").lower() != "д"
            or _SHORT_HOUSE_PREFIX.search(text[:match.start()]) is not None)


def _cue_document(cue: str) -> str | None:
    """Тип, названный существительным подсказки, или None, если его там нет.

    Слово, а не подстрока, — и та же таблица, из которой собрано окно
    (`_CUE_NUMBER`): два отдельно написанных перечня однажды разойдутся, и
    разойдутся именно здесь — окно впустит существительное, которого чтение не
    знает, а тогда тип не назван, и кусок спрашивается без сужения."""
    for kind, pattern in _CUE_DOCUMENT_RE:
        if pattern.search(cue):
            return kind
    return None


def _cue_kind(cue: str) -> tuple[str | None, str | None]:
    """What the cue says about the fragment: the identifier's type and whether
    the digits are its start or its end."""
    if cue.startswith("*"):
        return "CARD", "end"
    if cue.startswith("контрольн"):
        return "SNILS", "end"
    if cue.startswith("сери"):
        # Серия бывает только у паспорта; существительное её лишь подтверждает.
        return _cue_document(cue) or "PASSPORT", "start"
    if cue.startswith("номер"):
        # «НОМЕР» САМ ПО СЕБЕ ТИПА НЕ НАЗЫВАЕТ, и голым он остаётся тем же
        # неназванным куском, что и раньше. Тип здесь называет только
        # существительное, а оно в окно пущено лишь из `_CUE_DOCUMENTS`.
        document = _cue_document(cue)
        return (document, "end") if document else (None, None)
    if cue.startswith("последн") or cue.startswith("заканчива"):
        document = _cue_document(cue)
        return (document, "end") if document else (None, "end")
    return None, None


def _restore_cued_numbers_spans(
        text: str, vault: Vault,
        resolved_tokens: list[tuple[int, int, str]] | None = None,
) -> list[tuple[int, int, str]]:
    # A NUMBER INSIDE A WHOLE ADDRESS OR TOKEN IS NOT A FRAGMENT. «кв. 83» in
    # «Кинешму, ул. Озёрную 96, кв. 83» belongs to the token the inflected
    # window restores as one piece; replacing its flat here first broke the
    # window's key and the address came back as «ул. Баумана 5, ул. ул. …».
    # The whole framing — house, building, entrance, flat tails included —
    # because `_PLACE_RUN` stops at the street and «корп. 3» after it is part
    # of the same token; touched here first, the window's key no longer
    # matched and the address came back with the fake's building.
    protected: list[tuple[int, int]] = []
    for m in _PLACE_RUN.finditer(text):
        framings = _place_windows(text, m.start(), m.end())
        protected.append((min(s for s, _ in framings), max(e for _, e in framings)))
    # A regex shape alone is not a bound token. Its broad numeric alternatives
    # also match an isolated house/flat digit and used to block the very role
    # cues that license it (notably 'д.' / 'кв.'). Reuse already RESOLVED whole
    # tokens from the main pass; direct callers compute that same evidence once.
    bound = _restore_tokens_spans(text, vault) if resolved_tokens is None else resolved_tokens
    protected += [(start, end) for start, end, _ in bound]
    spans: list[tuple[int, int, str]] = []
    for match in _CUE_NUMBER.finditer(text):
        if not _licensed_number_cue(text, match):
            continue
        number = match.group("num")
        digits = re.sub(r"\D", "", number)
        if not digits:
            continue
        if any(a <= match.start("num") and match.end("num") <= b for a, b in protected):
            continue
        cue = match.group("cue").lower()
        replacement: str | None = None
        if cue.startswith(_HOUSE_CUES):
            # РОЛЬ НАЗЫВАЕТ САМА ПОДСКАЗКА, И ОНА ЖЕ ЕДЕТ В ВОПРОС (Б29).
            # Раньше роль выводилась из СОДЕРЖИМОГО найденной подмены — «в
            # какой её части стоят эти цифры», — то есть владельца искали
            # сперва, а роль подгоняли потом: «кв. 26» находило подмену, у
            # которой 26 стоит в номере дома, и заказчик получал чужой дом
            # под видом своей квартиры. Спрашивается то же слово, которым
            # спрашивает сигнал (`_CUE_ROLES`), чтобы два ответа не разошлись.
            role = _CUE_ROLES.get(cue[:2], "house")
            token = vault.place_owner(number, role)
            if token is not None:
                value, entity_type = vault.reveal(token)
                if value and entity_type == "LOC":
                    real_roles = morph_places.split_roles(value)
                    if role and real_roles.get(role):
                        replacement = morph_places.part_in_form_of(number, real_roles[role], role)
        else:
            if len(digits) < 2:
                continue
            kind, position = _cue_kind(cue)
            # НАЗВАННЫЙ ТИП ОТВЕЧАЕТ ИЛИ НЕ ОТВЕЧАЕТ НИКТО (Б29). Здесь стоял
            # повтор без типа на промахе типизированного поиска, и он
            # перечёркивал единственное, чем подсказка сужает вопрос: «номер
            # паспорта 2549» отдавал хвост НАСТОЯЩЕЙ КАРТЫ — значение чужого
            # типа, при 200 и пустом остатке. Свидетельство, которое можно
            # отбросить, когда оно мешает, свидетельством не является.
            owner = vault.digit_fragment_owner(digits, kind, position)
            if owner is not None:
                replacement = _same_shape(number, owner[0])
            # A masked card the model wrote as HEAD **** … TAIL keeps its TAIL
            # resolved by the `*` cue above; the HEAD sits BEFORE the mask and has
            # no backward cue. Only a card mask whose tail already resolved is
            # licensed, and only the first digits then resolve: `digit_fragment_owner`
            # still demands a unique conversation owner, so an unrelated number is
            # never guessed into a card prefix.
            if (replacement is not None and replacement != number
                    and kind == "CARD" and position == "end" and cue.startswith("*")):
                head = re.search(r'(?<![0-9])(\d{2,4})\s*$', text[:match.start()])
                if head is not None:
                    head_owner = vault.digit_fragment_owner(head.group(1), "CARD", "start")
                    if head_owner is not None and head_owner[0] != head.group(1):
                        spans.append((head.start(1), head.end(1),
                                      _same_shape(head.group(1), head_owner[0])))
        if replacement is not None and replacement != number:
            spans.append((match.start("num"), match.end("num"), replacement))
    return spans


# The ГОСТ plate alphabet was chosen precisely because every letter in it has a
# Latin twin — that is why a Russian plate is readable abroad. It is also why a
# model happily rewrites «Р984ОМ003» as «R984OM003»: to it the two are the same
# string in two scripts. The rewritten form is no longer the token, so the vault
# misses it and the customer's tool receives the fake.
#
# Seen in a persona run, once in four round trips, on a real tool call. Phones
# have had a second line of defence since the digit-signature reindex — a plate
# is the same failure with a different alphabet, and this is its equivalent.


def _restore_cued_numbers(text: str, vault: Vault) -> str:
    return _splice(text, _restore_cued_numbers_spans(text, vault))


_PLATE_FOLD = str.maketrans("ABEKMHOPCTYXabekmhopctyx", "АВЕКМНОРСТУХавекмнорстух")

# THE MODEL TRANSLITERATES BY SOUND, WE FOLDED BY SHAPE. The ГОСТ alphabet was
# picked so every letter has a Latin look-alike, and the fold above uses exactly
# that: «С» reads as «C», «Н» as «H». A model rewriting a plate does something
# else — it spells it: «С» becomes «S», «Н» becomes «N», «В» becomes «V». The
# two tables disagree on six letters out of twelve, so «С732ХК935» came back as
# «S732HK935», resolved to nothing, and a car that does not exist was written
# into a service centre's CRM with a 200 and an empty log.
#
# Both readings are offered on lookup and neither is authoritative: a miss costs
# one indexed point query, and only a plate is changed by either table.
_PLATE_SOUND = str.maketrans("AVEKMNORSTUHavekmnorstuh", "АВЕКМНОРСТУХавекмнорстух")

# A date the model rewrote. Unlike a plate this is not a character map — the
# COMPONENTS ARE REORDERED — so the candidate is rebuilt in the shape the token
# was minted in and looked up as itself. ISO is unambiguous (four digits lead);
# d/m/y and m/d/y are both offered when the year is last, and whichever resolves
# wins, because only one of them can be a token this customer holds.
_DATE_ANY = re.compile(r"^(\d{1,4})[.\-/ ](\d{1,2})[.\-/ ](\d{2,4})$")
_PLATE_SHAPE = re.compile(
    r"(?i)[АВЕКМНОРСТУХABCEHKMNOPRSTUVXY][ \t,\-]{0,2}\d{3}[ \t,\-]{0,2}"
    r"[АВЕКМНОРСТУХABCEHKMNOPRSTUVXY]{2}[ \t,\-]{0,2}\d{2,3}")
# A value that could be a date in digits — the cheap test before `_date_canonical`
# is asked, so a phone or a card number is never parsed as one.
_DATE_SHAPE = re.compile(r"^\s*\d{1,4}[.\-/ ]\d{1,2}[.\-/ ]\d{2,4}\s*$|^\s*\d{1,2}\s+[а-яёА-ЯЁ]+(?:\s+\d{4})?")

# THE TWO SURFACES A SEPARATOR OR A GLUED LABEL TAKES AWAY FROM `token_re` (W5/W6).
#
# `ru_pii_v6.TOKEN_PATTERNS` matches a VIN as `\b[0-9A-HJ-NPR-Z]{17}\b`; a four-group
# rewriting (`0ARK V4GV 0U3F 5832 7`) has no `\b` at either end of the 17 characters,
# and a label glued to the value (`номеркузова0ARK…`) removes the left one. The
# separators a regrouping inserts are notation, exactly as they are for every other
# identifier — `canonicalize` squeezes and uppercases a VIN — so the surface is
# squeezed here and asked of the vault as the token it claims to be.
#
# `IDENTITY_TOKEN_PATTERNS` anchors the ПТС/СТС shape with
# `(?<![0-9A-Za-zА-ЯЁа-яё])`, which a glued cue word defeats (the character left
# behind is Cyrillic). The copy below drops exactly that class from the lookbehind
# and keeps everything else — the two letters, the six digits, the trailing guard.
_VIN_SURFACE = re.compile(
    r"(?i)(?<![0-9A-Za-z])[0-9A-HJ-NPR-Z](?:[ \t\-]?[0-9A-HJ-NPR-Z]){16}(?![0-9A-Za-z])")
_VEHICLE_DOC_SURFACE = re.compile(
    r"(?<![0-9A-Za-z])\d{2}[ \t.,\-/]{0,2}[А-ЯЁA-Z]{2}[ \t.,\-/]{0,2}\d{6}"
    r"(?![0-9A-Za-zА-ЯЁа-яё])")


def _date_readings(value: str) -> list[str]:
    match = _DATE_ANY.match(value.strip())
    if not match:
        return []
    first, middle, last = match.groups()
    if len(first) == 4:
        return [f"{int(last):02d}.{int(middle):02d}.{first}"]
    if len(last) == 2:
        # A TWO-DIGIT YEAR reads by the same century rule the vault keys a
        # date with (`_date_canonical`): «82» is 1982, «02» is 2002.
        canonical = _date_canonical(value.strip())
        return [canonical] if len(canonical) == 10 else []
    if len(last) == 4:
        return [f"{int(first):02d}.{int(middle):02d}.{last}",
                f"{int(middle):02d}.{int(first):02d}.{last}"]
    return []


def _numeric_window(text: str, start: int, end: int) -> tuple[str, str]:
    """The maximal numeric run around [start:end], and the text before it.

    THE COUNTRY SIGN IS READ ON THE RUN, NOT ON THE PIECE. The verbatim seam
    matches a form this dialogue SHOWED — which, for a customer who wrote a bare
    ten digits, is a bare ten digits — so a «+3» the agent prepended to it stands
    OUTSIDE the match. A guard reading only the match would see ten digits and no
    sign at all, and the REAL digits went back under that invented prefix through
    this seam while the reformatted seam refused the very same run («+3
    9543836949» from a bare-ten substitute). `_NUM_RUN` is the window that seam
    offers the same string to, so both judge it the same way.
    """
    for match in _NUM_RUN.finditer(text):
        if match.start() <= start and end <= match.end():
            return text[match.start():match.end()], text[:match.start()]
    return text[start:end], text[:start]


def _restore_verbatim_spans(text: str, shown_forms: list[tuple[str, str, str]],
                            for_tool: bool = False) -> list[tuple[int, int, str]]:
    """Every occurrence of a form this conversation was shown, as the
    customer's literal string. Longest shown form first, non-overlapping,
    whole-word: «Ольховая 10» must not match inside «Ольховая 105».

    THE SEAM KNOWS ITS LEG. It used to be one seam for prose and for the tool
    argument, so an agent that copied a substitute character for character and an
    agent that changed one character in it received DIFFERENT values for the same
    field — the asymmetry that named the class. In PROSE the customer's literal
    string is the answer (it is what he would have got without us); in an
    ARGUMENT the value is the vault's and the notation is the agent's, rendered
    through the same interface every other seam uses."""
    spans: list[tuple[int, int, str]] = []
    for shown, original, kind in shown_forms:
        if not shown:
            continue
        # A numeric address LEAF is not a self-identifying literal. It was
        # licensed by its source role (house/flat), which this string-only table
        # does not carry into a new occurrence. Replacing it here rewrites IDs,
        # counts, list indices and even the prefix of a reformatted phone.
        # Restore such projections only via the existing role-aware address
        # object join or the cued-number resolver, never by substring identity.
        if kind == "LOC" and shown.strip().isdecimal():
            continue
        matches = list(re.finditer(re.escape(shown), text))
        if not matches and kind == "PLATE":
            # A PLATE IS THE SAME CAR IN EITHER CASE — `canonicalize` says so —
            # and a substitute shown in words or in the customer's lower case
            # comes back upper-cased. The case is not a different form here, as
            # it would be for a name; it is the same number.
            matches = list(re.finditer(re.escape(shown), text, re.IGNORECASE))
        for match in matches:
            start, end = match.start(), match.end()
            written: str = text[start:end]
            # A malformed country-code sign is not a form to restore under: the
            # shown «+79795553322» inside «++79795553322» would put the real
            # digits under the doubled sign (C02). Leave the agent's string.
            # A PHONE IS JUDGED ON ITS WHOLE RUN, because what makes a sign
            # malformed or invented is what stands BEFORE the last ten digits —
            # and that may lie outside the match. `shown_form` says the run IS
            # the form this dialogue showed, so its leading identity is the
            # customer's own prefix mirrored at the mint, not the agent's
            # invention.
            if kind == "PHONE":
                surface, before = _numeric_window(text, start, end)
            else:
                surface, before = written, text[:start]
            if _malformed_phone_sign(surface, before, shown_form=(surface == shown),
                                     phone=(kind == "PHONE")):
                continue
            if start > 0 and text[start - 1].isalnum() and shown[0].isalnum():
                continue
            if end < len(text) and text[end].isalnum() and shown[-1].isalnum():
                continue
            if any(start < b and a < end for a, b, _ in spans):
                continue
            if shown == original:
                # A self-mapping is the sticky ambiguity marker, not a value.
                spans.append((start, end, original))
                continue
            if for_tool:
                # THE VALUE IS THE VAULT'S, THE NOTATION IS THE AGENT'S. The
                # literal is kept only where the notation question does not
                # arise: a dictated rendering of a document whose leading zeroes
                # the copy carries exactly (see below) is not improved by being
                # re-parsed, and the tool-leg renderer is what decides the rest.
                copied_words: bool = kind in {"PHONE", "SNILS", "INN", "CARD", "PASSPORT"} and not any(
                    character.isdigit() for character in written + original)
                restored: str = (original if copied_words
                                 else _atomic_in_form_of(written, original, kind, for_tool=True))
                spans.append((start, end, restored))
                continue
            # A copied dictated rendering has stronger evidence than a new
            # parse: leading zeroes can split one original group into several
            # spoken groups. Reconstructing it loses the sender's original
            # grouping. Numeric output from a spoken original still renders
            # numerically; that is a changed form, not this literal-copy case.
            copied_words = kind in {"PHONE", "SNILS", "INN", "CARD", "PASSPORT"} and not any(
                character.isdigit() for character in shown + original)
            restored = original if copied_words else _atomic_in_form_of(written, original, kind)
            spans.append((start, end, restored))
    return spans


def _restore_tokens_spans(text: str, vault: Vault, for_tool: bool = False,
                          target: str = "") -> list[tuple[int, int, str]]:
    matches: list[re.Match[str]] = list(token_re().finditer(text))
    # THE v6 LEGAL FAMILY ASKS ITS OWN SHAPES TOO, AND IT HAS TO. `finditer` is
    # NON-OVERLAPPING and leftmost-first: the masked FSSP proceeding «ИП №
    # 4542450/74/44664-ИП» makes the identity MILITARY_ID shape (`[А-ЯЁ]{2} №?
    # \d{7}`) match the CUE AND THE FIRST GROUP as one candidate starting at
    # position 0, so the scan resumes after it and the real token is never seen —
    # the FAKE reaches the customer's tool with a 200 and an empty residual. The
    # dead candidate resolves to nothing and is skipped either way; adding the
    # family's own matches costs one scan and makes its restore independent of
    # whoever else matches nearby. Overlapping duplicates are dropped by span.
    seen_spans = {(match.start(), match.end()) for match in matches}
    for match in ru_pii_v6.LEGAL_TOKEN_RE.finditer(text):
        if (match.start(), match.end()) not in seen_spans:
            matches.append(match)
            seen_spans.add((match.start(), match.end()))
    # THE v6 FINANCE FAMILY ASKS ITS OWN SHAPES TOO, for the same reason the legal
    # family does: `finditer` is non-overlapping and leftmost-first, so a finance
    # token another shape matched AROUND — or a free-form run the bare-digit
    # patterns claimed first — would never become a candidate, and a substitute
    # that is not a candidate is a FAKE in the customer's tool with a 200. The
    # family's own scan is one extra pass; a dead candidate costs one indexed
    # point query and is never spliced (only a resolved candidate produces a
    # replacement).
    for match in ru_pii_v6.FINANCE_TOKEN_RE.finditer(text):
        if (match.start(), match.end()) not in seen_spans:
            matches.append(match)
            seen_spans.add((match.start(), match.end()))
    # THE v6 TELECOM/DEVICE FAMILY ASKS ITS OWN SHAPES TOO, for the same reason —
    # and here it is not a nicety. An IPv6 token and a MAC are matched by
    # `v5` shapes AROUND: `finditer` is non-overlapping and leftmost-first, so a
    # bare digit run claims the middle of `28ac:2a9::9` and a v5 MAC regex claims
    # a prefix of a hyphenated UUID, and the real token never becomes a candidate
    # at all — the FAKE reaches the customer's tool with a 200 and an empty
    # residual, which is the one failure this whole file is built to prevent.
    for match in ru_pii_v6.TELECOM_TOKEN_RE.finditer(text):
        if (match.start(), match.end()) not in seen_spans:
            matches.append(match)
            seen_spans.add((match.start(), match.end()))
    # THE v6 UTILITY/ACCOUNT/EDUCATION/TRAVEL FAMILY ASKS ITS OWN SHAPES TOO, for
    # the same reason — and here the reason is doubled. Its records are the LAST
    # patterns in `vault._token_re` on purpose (they are cue/key-typed rather than
    # format-anchored), and a bare 13-digit run is claimed by the ОГРН pattern
    # before them while a Latin handle is claimed by nothing; a substitute that is
    # not a candidate is a FAKE in the customer's tool with a 200 and an empty
    # residual, which is the one failure this whole file is built to prevent. A
    # dead candidate costs one indexed point query and is never spliced.
    for match in ru_pii_v6.UTILITY_TOKEN_RE.finditer(text):
        if (match.start(), match.end()) not in seen_spans:
            matches.append(match)
            seen_spans.add((match.start(), match.end()))
    # A VEHICLE IDENTIFIER WITH A SEPARATOR INSIDE, OR WITH ITS LABEL GLUED TO IT
    # (W5/W6). Two shapes the rest of this scan structurally cannot see:
    #
    #   * a VIN — `ru_pii_v6.TOKEN_PATTERNS` matches it as `\b[0-9A-HJ-NPR-Z]{17}\b`,
    #     so a model that regroups it as fours (`0ARK V4GV 0U3F 5832 7`, check A40)
    #     or that receives the label glued to it (`номеркузова0ARK…`, A43) leaves
    #     no `\b` at the run's edge and no candidate at all — the FAKE reaches the
    #     customer's tool with a 200. The surface is squeezed to its 17 characters
    #     and asked of the vault as an exact token, which is the identity
    #     `canonicalize` already keys a VIN by (`re.sub(r"\s+","",value).upper()`).
    #   * a ПТС/СТС — `IDENTITY_TOKEN_PATTERNS` anchors it with
    #     `(?<![0-9A-Za-zА-ЯЁа-яё])`, and a glued cue word leaves exactly a
    #     Cyrillic letter there («ПТС59ЛО037992», A44), so the shape never fires.
    #     The relaxed copy drops only that one class of the lookbehind; the
    #     resolution is still the identity signature, so a spelling the vault does
    #     not hold costs one indexed point query and can never restore a value.
    #
    # BOTH ARE MISS-COST-ONLY: nothing is spliced unless the vault answers.
    for match in _VIN_SURFACE.finditer(text):
        squeezed = re.sub(r"[ \t\-]", "", match.group())
        if (match.start(), match.end()) in seen_spans or not squeezed:
            continue
        matches.append(_Whole(match.start(), match.end(), squeezed))
        seen_spans.add((match.start(), match.end()))
    for match in _VEHICLE_DOC_SURFACE.finditer(text):
        if (match.start(), match.end()) in seen_spans:
            continue
        matches.append(_Whole(match.start(), match.end(), match.group()))
        seen_spans.add((match.start(), match.end()))
    spoken_dates: set[str] = set()
    # A DATE SAID IN WORDS is a token too, since a spoken date of birth is
    # replaced by a spoken substitute; `TOKEN_RE` knows the digit shapes only,
    # so the spoken-date arm of the detector supplies the candidates. A miss
    # costs one indexed lookup, as every other candidate does.
    if ASSETS.is_loaded:
        taken = [(m.start(), m.end()) for m in matches]
        for spoken_date in ASSETS.get().quasi.text_date.finditer(text):
            if not any(a < spoken_date.end() and spoken_date.start() < b for a, b in taken):
                matches.append(spoken_date)
                spoken_dates.add(spoken_date.group())
        matches.sort(key=lambda m: m.start())
    if not matches:
        return []
    candidates = {match.group() for match in matches}
    # Every way the model might have rewritten a token, offered alongside the
    # token itself. A miss costs one indexed point query; a hit is the difference
    # between the customer's tool receiving a real value and receiving a fake.
    readings: dict[str, list[str]] = {}
    for value in candidates:
        alternates = [value.translate(_PLATE_FOLD), value.translate(_PLATE_SOUND)]
        # THE AGENT'S LETTER CASE IS NOT PART OF THE KEY: a token is minted
        # in one case and the agent may write it in another («HUTHDHTQ@…»,
        # «е940ае613»); the lookup asks for the minted spelling as well.
        alternates.extend([value.lower(), value.upper(),
                           value.upper().translate(_PLATE_FOLD), value.upper().translate(_PLATE_SOUND)])
        alternates.extend(_date_readings(value))
        # A DATE WITH THE MONTH IN WORDS reads to its canonical too: the
        # substitute was minted as «15 апреля 1990 года», the agent dropped
        # «года», and the exact token no longer matched — the canonical is
        # what `date_owner` is keyed by.
        if value in spoken_dates or (_DATE_SHAPE.match(value) and not _DATE_ANY.match(value.strip())):
            canonical = _date_canonical(value)
            if len(canonical) == 10:
                alternates.append(canonical)
        readings[value] = [alt for alt in alternates if alt != value]

    asked = candidates | {alt for group in readings.values() for alt in group}
    typed = vault.detokenize_many_typed(asked, for_tool)
    values = {written: value for written, (_, value) in typed.items()}
    types = {written: kind for written, (kind, _) in typed.items()}
    # A PLATE RESOLVES BY ITS CONTENT, NOT BY ITS SPELLING — the same second line
    # of defence the phone got from its digit signature. A plate is quoted with
    # the customer's separators and letter case (`_token_for_text` mirrors them),
    # the agent rewrites it into the ГОСТ glued form or spells it in another
    # alphabet, and the exact surface is then no token at all: the fake left for
    # the customer's validator with a 200 and an empty log. One indexed point
    # query per plate-shaped candidate; a miss costs the same as the lookup that
    # already ran.
    plates: dict[str, tuple[str, str]] = {}
    signatures = {notation.plate_signature(value) for value in candidates
                  if _PLATE_SHAPE.fullmatch(value)}
    signatures.discard("")
    if signatures:
        # `resolve_digit_signatures_typed` отдаёт (ТИП, ЗНАЧЕНИЕ), а шов ниже
        # работает парой (значение, тип) — как `resolved()`. Порядок здесь и есть
        # то место, где перепутанная пара отдала бы инструменту строку «PLATE»
        # вместо номера: тест `test_notation_symmetry` ловит именно её.
        plates = {signature: (hit[1], hit[0]) for signature, hit in
                  vault.resolve_digit_signatures_typed(signatures, for_tool).items()
                  if hit[0] == "PLATE"}
    # A DATE THE VAULT HOLDS IN WORDS. The agent writes «1955-08-17» for the
    # substitute «семнадцатого августа пятьдесят пятого года»; the reading
    # «17.08.1955» is no token, but it is the canonical the vault indexed the
    # spoken substitute under.
    for value in candidates:
        for alternate in (value, *readings.get(value, ())):
            if alternate not in values and _DATE_ANY.match(alternate):
                owner = vault.date_owner(alternate, for_tool)
                if owner is not None:
                    values[alternate] = owner
                    types[alternate] = "DOB"

    # AN IDENTITY DOCUMENT RESOLVES BY ITS CONTENT TOO — its letters included.
    # «АК № 1234567» shown by the mint comes back as «АК1234567» or «АК 1234567»,
    # and the exact token is then no token at all: the FAKE reaches the customer's
    # tool with a 200 and an empty residual. The shape names WHICH LABELS the
    # candidate could be (`identity_signatures`), and the label is part of the
    # signature because «82 1234567» is one document as a ВНЖ and another as a
    # passport. A wrong guess costs one indexed point query, exactly as the plate
    # block above does. Mirrors `vault._digit_signatures`.
    #
    # MORE THAN ONE READING IS NORMAL, and it is not an accident of the shape: the
    # registry gives BIRTH_CERT and CIVIL_ACT_CERT the SAME grammar («как
    # BIRTH_CERT»), so no spelling can tell a birth certificate from a marriage
    # one. Naming ONE label would lose whichever row the guess did not name — the
    # failure `legal_signatures` already answers the same way: ask every reading as
    # its own indexed point query and keep a hit only when the vault's recorded
    # label is the label the signature was proposed under.
    identities: dict[str, tuple[str, str]] = {}
    identity_asked: dict[str, tuple[str, str]] = {}
    for value in candidates:
        for signature, label in ru_pii_v6.identity_signatures(value):
            identity_asked.setdefault(signature, (value, label))
    if identity_asked:
        for signature, hit in vault.resolve_digit_signatures_typed(
                set(identity_asked), for_tool).items():
            written, label = identity_asked[signature]
            if hit[0] == label:
                identities[written] = (hit[1], label)

    # THE v6 LEGAL FAMILY RESOLVES BY ITS CONTENT TOO, AND IT MAY HAVE MORE THAN
    # ONE READING. A stripped «2-13/2015» and a stripped FSSP alternative-2 are
    # both bare digit runs, so — unlike the identity documents — naming ONE label
    # would lose whichever row the guess did not name. `legal_signatures` proposes
    # every reading the spelling allows; each is asked as its own indexed point
    # query, and a hit is kept only when the vault's recorded label is the label
    # the signature was proposed under. A wrong reading costs one query and can
    # never restore another type's value. Mirrors `vault._digit_signatures`.
    legal_asked: dict[str, tuple[str, str]] = {}
    for value in candidates:
        for signature, label in ru_pii_v6.legal_signatures(value):
            legal_asked.setdefault(signature, (value, label))
    if legal_asked:
        for signature, hit in vault.resolve_digit_signatures_typed(
                set(legal_asked), for_tool).items():
            written, label = legal_asked[signature]
            if hit[0] == label:
                identities[written] = (hit[1], label)

    # THE v6 FINANCE FAMILY RESOLVES BY ITS CONTENT TOO, AND ITS SHAPES OVERLAP BY
    # CONSTRUCTION. Eight of the ten records are free-form numbers, so one
    # spelling («12345/2024») is a MEDCARD_NUMBER shape and, at another digit
    # count, a PRESCRIPTION_NUMBER shape. `finance_signatures` proposes EVERY
    # reading as its own indexed point query and a hit is kept only when the
    # vault's recorded label is the label the signature was proposed under — so a
    # wrong reading costs one query and can never restore another type's value.
    # The digit-only members (`ELN_NUMBER`, a stripped medcard) are resolved by the
    # digit-signature path below, exactly as a stripped cadastral is; mirrors
    # `vault._digit_signatures`.
    finance_asked: dict[str, tuple[str, str]] = {}
    for value in candidates:
        for signature, label in ru_pii_v6.finance_signatures(value):
            finance_asked.setdefault(signature, (value, label))
    if finance_asked:
        for signature, hit in vault.resolve_digit_signatures_typed(
                set(finance_asked), for_tool).items():
            written, label = finance_asked[signature]
            if hit[0] == label:
                identities[written] = (hit[1], label)

    # THE v6 TELECOM/DEVICE FAMILY RESOLVES BY ITS CONTENT TOO, AND IT HAS TO:
    # its identity is hex LETTERS as well as digits, so a MAC with its separators
    # re-arranged, a UUID the agent re-cased and an IPv6 address the agent
    # re-compressed all stop being exact tokens. `telecom_signatures` proposes the
    # readings of each candidate spelling and every reading is asked as its own
    # indexed point query; a hit is kept only when the vault's recorded label is
    # the label the signature was proposed under, so a wrong reading can never
    # restore another type's value. Mirrors `vault._digit_signatures`.
    telecom_asked: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {}
    for value in candidates:
        # NOTE THE NAME: `readings` above is the AGENT'S REWRITINGS of a token
        # (separator/case variants of the same string), which is a different
        # question from the READINGS of a spelling in this family's shape
        # language. The two must not be confused, so this one is named apart.
        telecom_readings = ru_pii_v6.telecom_signatures(value)
        for label, signature in telecom_readings:
            telecom_asked.setdefault(signature, (value, tuple(telecom_readings)))
    if telecom_asked:
        for signature, hit in vault.resolve_digit_signatures_typed(
                set(telecom_asked), for_tool).items():
            written, telecom_readings = telecom_asked[signature]
            for label, _signature in telecom_readings:
                if hit[0] == label:
                    identities[written] = (hit[1], label)
                    break

    # THE v6 UTILITY/ACCOUNT/EDUCATION/TRAVEL FAMILY RESOLVES BY ITS CONTENT TOO,
    # AND IT HAS TO, for the reason the four families above give: a ЕЛС's Cyrillic
    # series, a login's letters and a CDP code are content, so a re-cased,
    # re-grouped or separator-stripped substitute stops being an exact token. And
    # its shapes overlap by construction — a six-to-twelve digit run is a
    # UTILITY_ACCOUNT reading AND an ACCESS_PASS reading, and «145-ТД» is a
    # contract AND a letter-bearing account — so EVERY reading is proposed, each
    # asked as its own indexed point query, and a hit is kept only when the vault's
    # recorded label is one of the labels the spelling was read under. `setdefault`
    # would keep only the FIRST label of a shared signature (a thirteen-digit run
    # on «1[0-4]» is both a diploma and an air ticket), so the map carries the whole
    # reading list exactly as the telecom block above does. Mirrors
    # `vault._digit_signatures`.
    utility_asked: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {}
    for value in candidates:
        utility_readings = ru_pii_v6.utility_signatures(value)
        for signature, _label in utility_readings:
            utility_asked.setdefault(signature, (value, tuple(utility_readings)))
    if utility_asked:
        for signature, hit in vault.resolve_digit_signatures_typed(
                set(utility_asked), for_tool).items():
            written, utility_readings = utility_asked[signature]
            for _signature, label in utility_readings:
                if hit[0] == label:
                    identities[written] = (hit[1], label)
                    break

    def resolved(written: str) -> tuple[str, str | None] | None:
        if written in values:
            return values[written], types.get(written)
        for alternate in readings.get(written, ()):
            if alternate in values:
                return values[alternate], types.get(alternate)
        if plates and _PLATE_SHAPE.fullmatch(written):
            signature = notation.plate_signature(written)
            if signature in plates:
                return plates[signature]
        if written in identities:
            return identities[written]
        return None

    spans: list[tuple[int, int, str]] = []
    for match in matches:
        surface = match.group()
        # A malformed country-code sign is not a phone we may restore under: a
        # token matching from the SECOND plus of «++79795553322» put the real
        # digits under the doubled sign (C02), and an invented single-digit
        # identity does the same under a sign a dialer accepts. Leave it
        # untouched; `surviving_substitutes` names it.
        # ON THE WHOLE RUN, LIKE EVERY OTHER SEAM: `TOKEN_RE` matches the bare
        # TEN inside a run the agent prefixed («+3 9543836949» is a `\d{10}` for
        # it), and judging that ten alone restored the real digits under the
        # invented prefix through THIS seam.
        window, before = _numeric_window(text, match.start(), match.end())
        hit = resolved(surface)
        # ONLY A RUN THAT RESOLVED TO A PHONE can wear an invented country
        # identity: `_invented_phone_prefix` is the one rule here that needs the
        # vault's answer, and the restorer's own answer is asked for it — an
        # eleven-digit СНИЛС the agent put a sign in front of is a form, not a
        # country code, and it restores as before.
        if _malformed_phone_sign(window, before,
                                 phone=hit is not None and hit[1] == "PHONE"):
            continue
        if hit is not None:
            value, kind = hit
            # A DATE COMES BACK IN THE AGENT'S NOTATION — «2 июня 1975» where
            # the agent wrote «19 июля 1975», «1975-06-02» where it wrote ISO,
            # «2.6.75» where it kept the customer's short form — and in the
            # customer's own words when the notation is already the same. The
            # vault holds the canonical and the original; the form belongs to
            # whoever wrote the substitute, on both legs. Decided BEFORE the
            # digit splice: a date is not an identifier, and laying its digits
            # into the surface's slots padded «10.4.82» to «10.04.82».
            canonical = _date_canonical(value) if kind in {"DOB", "DATE"} else ""
            if len(canonical) == 10 and _date_canonical(surface):
                value = _atomic_in_form_of(surface, value, kind, for_tool=for_tool, target=target)
            elif kind in {"PHONE", "SNILS", "INN", "CARD", "PASSPORT", "EMAIL", "PLATE",
                          # v6: the content is the vault's, the notation is the
                          # agent's — separators, grouping and letter case.
                          "IMEI", "ICCID", "EPTS", "UIN", "LOYALTY",
                          "IBAN", "LOAN_UID", "VIN",
                          # the v6 identity documents, same rule: a certificate's
                          # series, a ПТС's letters and the document's grouping.
                          "INTL_PASSPORT", "BIRTH_CERT", "CIVIL_ACT_CERT",
                          "MILITARY_ID",
                          "DRIVER_LICENSE", "RESIDENCE_PERMIT", "VEHICLE_DOC",
                          # the v6 legal family, same rule: the content is the
                          # vault's, the separators, letter case and script are
                          # the agent's.
                          *ru_pii_v6.LEGAL_LABELS,
                          # the v6 finance family, same rule for the same reason:
                          # a policy's series letters and a claim's «У-» prefix are
                          # the vault's content, the separators and the case are
                          # whoever wrote the mention.
                          *ru_pii_v6.FINANCE_LABELS,
                          # the v6 telecom/device family, same rule: the octets,
                          # the hex digits and the group count are the vault's content
                          # on the way back, and the notation belongs to the agent that
                          # wrote the substitute.
                          *ru_pii_v6.TELECOM_FAMILY_LABELS,
                          # the v6 utility/account/education/travel family, same
                          # rule: a ЕЛС's series letters, a login's handle and the
                          # separators of a diploma or a pass are the vault's
                          # content on the way back, and the grouping and case
                          # belong to whoever wrote the substitute.
                          *ru_pii_v6.UTILITY_LABELS}:
                value = _atomic_in_form_of(surface, value, kind, for_tool=for_tool, target=target)
            elif for_tool and kind == "NAME":
                # THE EXACT TOKEN, RE-CASED OR NOT: the agent wrote the
                # nominative it was shown («Николай Сорокин» for a substitute
                # the text carried as «николай сорокин»), so the real name goes
                # back in the nominative and in the agent's letter case — the
                # same rule the inflected windows apply.
                value = agent_form.name_cased_like(_person_in_case_of(value, surface, vault), surface)
            elif for_tool and ("@" in surface or _PLATE_SHAPE.fullmatch(surface)):
                # An e-mail or a plate comes back in the agent's letter case:
                # the value is the customer's, the spelling of the field is
                # the agent's, as for every other type.
                value = agent_form.cased_like(value, surface)
            elif for_tool:
                value = _digits_in_form_of(surface, value)
            spans.append((match.start(), match.end(), value))
    return spans


def _restore_tokens(text: str, vault: Vault, for_tool: bool = False) -> str:
    return _splice(text, _restore_tokens_spans(text, vault, for_tool))


def _restore_reformatted_spans(text: str, vault: Vault,
                         for_tool: bool = False, field_key: str = "",
                         target: str = "") -> list[tuple[int, int, str]]:
    """Numeric tokens the model rewrote (+7… -> 8…, separators stripped) no longer
    match their minted shape, so they are resolved by digit signature instead."""
    normalized_text: str = normalize(text)
    runs = [(match, re.sub(r"\D", "", match.group())) for match in _NUM_RUN.finditer(normalized_text)]
    # ПОЛЕ, СОСТОЯЩЕЕ ТОЛЬКО ИЗ ЧИСЛА, — ЭТО ЧАСТЬ ЗНАЧЕНИЯ, А НЕ ЧИСЛО В ТЕКСТЕ.
    # `_NUM_RUN` намеренно требует длинного прогона: короткое число в прозе — это
    # обычно количество, и подменять его настоящими цифрами значило бы называть
    # персональные данные там, где их не называли. Но «серия паспорта» и
    # «последние четыре цифры» — это ОТДЕЛЬНЫЕ поля схемы, и в них не стоит
    # ничего, кроме числа. Три цифры минимум: группа СНИЛС — три, серия и хвост
    # телефона — четыре, а двузначное — это «количество: 12».
    if for_tool and not runs and _WHOLE_NUMBER.fullmatch(text.strip()):
        stripped = text.strip()
        offset = text.index(stripped)
        runs = [(_Whole(offset, offset + len(stripped), stripped),
                 re.sub(r"\D", "", stripped))]
    if not runs:
        return []
    # THE FIELD'S OWN DECLARATION IS WHAT NAMES A DIGIT'S EDGE (класс Д). The
    # positional slice of a substitute's digits is licensed only by a named
    # place — `series`/`number`/`last4` — never by «the field held a number».
    edge_type, edge = (structured.key_edge(field_key, ASSETS.get().structured)
                       if for_tool and field_key else (None, None))
    candidates: set[str] = set()
    for _, digits in runs:
        candidates.add(digits)
        if len(digits) >= 10:
            candidates.add(digits[-10:])
    resolved = vault.resolve_digit_signatures_typed(candidates, for_tool)
    # БЕЗ РАННЕГО ВОЗВРАТА. Пустая выборка по сигнатурам — это ровно тот случай,
    # ради которого заведён разбор куска ниже: агент положил в поле часть
    # подмены, и целой сигнатуры у неё нет по построению.
    spans: list[tuple[int, int, str]] = []
    for match, digits in runs:
        surface = text[match.start():match.end()]
        # Full signature wins over the phone last-10 fallback. The fallback is
        # PHONE-shaped only: ten digits is the domestic tail, eleven is the
        # country-coded form, and a twelve-digit run is NEVER a phone — a phone
        # the model extended with one digit is twelve, and running its trailing
        # ten through the fallback laid the REAL value under the agent's
        # spurious digit (E02: «979795553322» came back «979162148803»).
        hit = resolved.get(digits)
        if hit is None and 10 <= len(digits) <= 11:
            hit = resolved.get(digits[-10:])
        if hit is None:
            # ВЕДУЩИЙ НОЛЬ, СНЯТЫЙ У ГРУППЫ (W7). Третий вопрос после цифровой
            # подписи и позиционного куска, и он задан только там, где первые
            # два молчат. Прогон, укороченный снятием нуля у группы, не лежит
            # внутри цифр подмены ни на одном смещении, поэтому `_digit_rows` его
            # не видит, а цифровая подпись не равна цифрам подмены. Разделители
            # записи при этом уцелели — таблица снимает ноль, но не пробелы, —
            # и скелет записи (`vault.zero_grouped`) отвечает, каким написанием
            # прогон был. `resolve_zero_grouped_typed` требует ЕДИНСТВЕННОГО
            # кандидата и отказывает, как только скелет носят две подмены, так
            # что цена ложного ответа не покупается ничем: промах — один запрос.
            key = zero_grouped(surface)
            grouped = vault.resolve_zero_grouped_typed({key}, for_tool) if "|" in key else {}
            hit = grouped.get(key)
        # A MALFORMED COUNTRY-CODE SIGN is not a phone form we may splice under.
        # «+8…» and «++…» came back with the REAL digits laid under the agent's
        # broken sign («+89162148803», «++79162148803») — a hybrid a dialer
        # refuses (C02) — nor an INVENTED single-digit identity: the splice kept
        # whatever stood before the last ten digits, so «+3 954 383-69-49» came
        # back «+3 962 056-61-63», the customer's REAL digits under a country
        # code nobody wrote, with an empty residual. Leave the run untouched; it
        # is the agent's own string and the residual detector names it.
        # AND ONLY WHAT RESOLVED TO A PHONE MAY WEAR AN INVENTED COUNTRY
        # IDENTITY: an eleven-digit СНИЛС the agent put a sign in front of is a
        # form, not a country code, and it restores as before.
        if _malformed_phone_sign(surface, text[:match.start()],
                                 phone=hit is not None and hit[0] == "PHONE"):
            continue
        if hit is not None:
            kind, value = hit
            # THE TEMPORARY SECRETS ARE NOT RESOLVED BY DIGIT SIGNATURE. The
            # signature index is TYPE-FREE and this path answers ANY field whose
            # whole content is a number — that is safe for a ten-digit INN and
            # not for a class whose domain is a THOUSAND values: a business
            # «quantity: 698» that happens to equal a card-code substitute would
            # come back carrying the customer's real code, silently, with a 200
            # (A7/O-SECRET-8). The class has its own pass, gated on the SAME
            # evidence that minted the substitute (`cvc.restore_spans`), and a
            # candidate that reaches no context stays standing and is named as a
            # residual. This is a NARROWING of one path for two labels, not a
            # change to how any other type resolves.
            if kind in cvc.LABEL_SET:
                continue
            value = _atomic_in_form_of(text[match.start():match.end()], value, kind,
                                       for_tool=for_tool, target=target)
            spans.append((match.start(), match.end(), value))
            continue
        # КУСОК ПОДМЕНЫ — ТОЖЕ НАША ПОДМЕНА. Схема просит серию паспорта без
        # номера, оператор переспрашивает последние четыре цифры телефона — и
        # такой кусок целая сигнатура не находит, поэтому он уходил в инструмент
        # КАК ЕСТЬ, то есть фейком, с кодом 200 и пустыми остатками.
        #
        # Только на плече аргумента: в прозе кусок числа — это чаще всего просто
        # число, и подменять его настоящими цифрами значило бы раскрывать
        # персональные данные там, где их не называли.
        # IN PROSE TOO, for a run this long. `_NUM_RUN` admits only seven or
        # more characters of digits and separators, and a СНИЛС the model
        # spelled digit by digit for the customer — «4 4 5 3 0 1 9 2 5,
        # контрольное число 59» — is exactly that: a fragment of OUR substitute
        # shown as the customer's own number (v4 small run, 22 of 59 replies
        # the judge flagged). A short bare number stays untouched here; the
        # cue-gated path below is where «дом 74» is decided.
        if len(digits) < _FRAGMENT_DIGIT_FLOOR:
            continue
        # THE TYPE TRAVELS ONLY WITH A NAMED EDGE. The whole-number resolution
        # (`_normalizing_hole`) is about identity, and identity is type-free: the
        # same number written as an ИНН and as a СНИЛС must stay ambiguous and
        # refuse, not be narrowed by the field's key. The type narrows ONLY the
        # positional slice, and only a named edge licenses a slice at all.
        owner = vault.digit_fragment_owner(digits, edge_type if edge else None, edge)
        if owner is not None:
            spans.append((match.start(), match.end(),
                          _numeric_glyphs_like(text[match.start():match.end()],
                                               _same_shape(match.group(), owner[0]))))
    return spans


def _restore_reformatted(text: str, vault: Vault,
                         for_tool: bool = False) -> str:
    return _splice(text, _restore_reformatted_spans(text, vault, for_tool))


def _spoken_identifier_hits(text: str, vault: Vault,
                            for_tool: bool) -> list[_ResolvedSpan]:
    """Resolve whole dictated substitutes by indexed identity, never by a fragment."""
    if not ASSETS.is_loaded:
        return []
    runs: list[tuple[int, int, str]] = [
        (start, end, spoken.run_to_digits(words))
        for start, end, words in spoken.numeral_runs(text)]
    candidates: set[str] = {digits for _, _, digits in runs if len(digits) >= 10}
    candidates |= {"7" + digits[1:] for digits in candidates
                   if len(digits) == 11 and digits.startswith("8")}
    if not candidates:
        return []
    resolved = vault.resolve_digit_signatures_typed(candidates, for_tool)
    spans: list[_ResolvedSpan] = []
    for start, end, digits in runs:
        key: str = "7" + digits[1:] if len(digits) == 11 and digits.startswith("8") else digits
        hit = resolved.get(digits)
        if hit is None and key != digits:
            phone_hit = resolved.get(key)
            hit = phone_hit if phone_hit is not None and phone_hit[0] == "PHONE" else None
        if hit is None:
            continue
        kind, value = hit
        spans.append(_ResolvedSpan(start, end, value, kind))
    return spans


def _restore_spoken_identifier_spans(text: str, vault: Vault,
                                    for_tool: bool) -> list[tuple[int, int, str]]:
    """Apply the current spoken form after whole-identity resolution."""
    return [(hit.start, hit.end, _atomic_in_form_of(
        text[hit.start:hit.end], hit.value, hit.entity_type, for_tool=for_tool))
        for hit in _spoken_identifier_hits(text, vault, for_tool)]


def _same_shape(model: str, digits: str) -> str:
    """Настоящие цифры В РАЗДЕЛИТЕЛЯХ, которые расставил агент.

    «90 71» и «45 09» — одна форма и разное содержимое; вернуть «4509» значило
    бы переписать поле его схемы своим представлением о том, как пишут серию.
    """
    out, index = [], 0
    for char in model:
        if char.isdigit() and index < len(digits):
            out.append(digits[index])
            index += 1
        elif not char.isdigit():
            out.append(char)
    return "".join(out) + digits[index:]


# A value that is nothing but digits and the separators people put between them:
# a phone, a СНИЛС, a passport, a card, a date. A name or an address never
# matches, and that is the guard — splicing real digits into a FAKE street's
# text would hand the tool an address that exists nowhere.
_NUMERIC_FORM = re.compile(r"[+(]?\d[\d\s().\-/]*\d")


def _plate_in_form_of(written: str, value: str, for_tool: bool = False) -> str:
    """Plate notation — the interface's answer, kept under its old name.

    The renderer moved to `notation` (one decision point for every type); this
    alias exists so no caller keeps a second implementation of the same
    question."""
    return notation.plate_in_form_of(written, value, for_tool=for_tool)


def _atomic_in_form_of(written: str, value: str, kind: str,
                       for_tool: bool = False, target: str = "") -> str:
    """Render resolved content in a mention's form, independent of its consumer.

    THE SEAM, NOT THE DECISION. Identity resolution supplies the type; the
    NOTATION is decided in `notation.render_like` and nowhere else, so the
    verbatim seam, the token seam and the mint cannot disagree about the same
    field — the disagreement that was class А. `for_tool` says which leg the
    mention is on: the tool cannot execute a dictated phrase, so there the
    leaf's notation wins over the sender's words. `target` is the leaf's
    SCHEMA-declared notation (класс Ж): when the tool schema names one
    («snils» = XXX-XXX-XXX YY), it overrides the sender's separators; empty
    means «not declared — do not guess».
    """
    return notation.render_like(value, written, kind, for_tool=for_tool, target=target)


def _numeric_in_form_of(written: str, value: str, kind: str,
                        target: str = "") -> str:
    """Процифровые документы — эталон, работавший и до класса А.

    PHONE, СНИЛС, ИНН, карта, паспорт: диктовка (`digits_in_words_like`) и
    разделители агента (`_same_shape`). Ничего не решает про нотацию листа —
    это делает `notation.render_like`, который сюда и приходит. `target` —
    объявленная схемой нотация листа (класс Ж): «snils» форсирует
    «XXX-XXX-XXX YY», без объявления нотацию держит агентская поверхность.
    """
    if kind == "PHONE":
        return _phone_in_form_of(written, value)
    if kind in {"INTL_PASSPORT", "BIRTH_CERT", "CIVIL_ACT_CERT", "MILITARY_ID",
                "DRIVER_LICENSE", "RESIDENCE_PERMIT", "VEHICLE_DOC"}:
        # THE v6 IDENTITY DOCUMENTS: letters AND digits, and the notation is the
        # separators and the letter case of whoever wrote the mention — the
        # customer on the IN leg, the agent on the OUT leg. One function for both
        # legs (`render_like_atomic`), because a second implementation is where
        # the two would start to disagree (класс А).
        #
        # A SURFACE WITH NO SEPARATOR AT ALL CARRIES NO NOTATION TO MIRROR. The
        # agent that wrote `4476444725` did not choose a grouping — it stripped
        # ours — and the answer is the customer's own form, which is what the
        # vault holds. Returning the digits we were handed would put a licence
        # number the customer never wrote into the field, and `test_product`
        # pins exactly that.
        if not any(not char.isalnum() for char in written):
            return value
        # No local import here: the module already binds `ru_pii_v6` at the top,
        # and a function-local import would make the name local to the WHOLE
        # function — the legal branch below reads the same name.
        return ru_pii_v6.render_like_atomic(value, written)
    if kind in ru_pii_v6.LEGAL_LABELS:
        # THE v6 LEGAL FAMILY: same rule, same function, for the same reason. A
        # case number is letters AND digits with separators that are the sender's
        # form; a cadastral number is digits with colons. `render_like_atomic`
        # moves every alphanumeric character and keeps every separator, so the
        # customer's «А31-2840/2013» and the agent's regrouped «А31/2840-2013»
        # both carry their own notation while the content never moves.
        if not any(not char.isalnum() for char in written):
            return value
        return ru_pii_v6.render_like_atomic(value, written)
    if kind in ru_pii_v6.FINANCE_LABELS:
        # THE v6 FINANCE FAMILY: the identical rule and the identical function.
        # «001SB12345678», «У-671-475136/25», «45 0012345678» — every one of them
        # is a run of letters and digits whose separators are the sender's form,
        # and `render_like_atomic` moves the content while keeping the layout. A
        # surface with no separator carries no notation to mirror and the vault's
        # own value is the answer, exactly as the two branches above state.
        if not any(not char.isalnum() for char in written):
            return value
        return ru_pii_v6.render_like_atomic(value, written)
    if kind in ru_pii_v6.TELECOM_FAMILY_LABELS:
        # THE v6 TELECOM/DEVICE FAMILY: letters AS WELL AS digits, so the same
        # function the identity and finance families use. A MAC's colons, a
        # UUID's hyphens and an IPv6 address's group count are the writer's
        # notation, and `render_like_atomic` moves the content (the hex digits,
        # the octets) while keeping the layout. A surface with no separator —
        # `951651234` for an address, a glued UUID — carries no notation to
        # mirror, and the vault's own value is the answer, which is exactly what
        # the digit-signature path already guarantees for a numeric token.
        if not any(not char.isalnum() for char in written):
            return value
        # AN ADDRESS THAT LAYS ITS OWN LAYOUT IS RETURNED AS IT IS (see
        # `_token_for_text`, where the same rule stops the MASK leg from mirroring
        # it a second time). An IPv4 fake is a whole reserved address and an
        # IPv4-MAPPED IPv6 fake is prefix + reserved tail, so their dots are in
        # the FAKE's places, not the source's: laying the real address into them
        # produced «951.65.12.34» for «95.165.12.34» — a real value the customer
        # never wrote, handed to the tool. An IPv6 fake is one hex character per
        # slot (the exception inside the exception), so it IS mirrored.
        if ru_pii_v6.telecom_own_layout(kind, written):
            return value
        return ru_pii_v6.render_like_atomic(value, written)
    if kind in ru_pii_v6.UTILITY_LABELS:
        # THE v6 UTILITY/ACCOUNT/EDUCATION/TRAVEL FAMILY: the same rule and the
        # same function. «60АА000593-01», «107724 0001234», «145-ТД», «21-0345» —
        # letters AND digits whose separators are the writer's form, on both legs.
        #
        # A SURFACE THAT CARRIES NEITHER A SEPARATOR NOR A LETTER HAS NO NOTATION
        # TO MIRROR: `1077240001234` is the same number however it is grouped, and
        # the vault's own value is the answer (the four branches above state the
        # same rule). BUT A LETTER IS A NOTATION OF ITS OWN for this family — a
        # ЕЛС, a login and a contract number vary by CASE where their separators are
        # fixed by the registry — so an all-alphanumeric surface that carries
        # letters IS mirrored, and the agent's case comes back. Without that half,
        # an agent that upper-cased a login got the customer's lower-case value.
        if not any(not char.isalnum() for char in written) and \
                not any(char.isalpha() for char in written):
            return value
        return ru_pii_v6.render_like_atomic(value, written)
    if kind in {"SNILS", "INN", "CARD", "PASSPORT",
                # the v6 digit-only checksum types: `_same_shape` lays the real
                # digits into the SEPARATORS the agent wrote, which is the whole
                # notation question for them.
                "IMEI", "ICCID", "EPTS", "UIN", "LOYALTY"}:
        model: str = normalize(written)
        digits: str = re.sub(r"\D", "", canonicalize(kind, normalize(value)))
        # СХЕМА ОБЪЯВИЛА НОТАЦИЮ ЛИСТА (DECISIONS-SPRINT.md §Класс Ж): «схема
        # говорит SNILS: XXX-XXX-XXX YY — рендерим в этой нотации». Только тогда,
        # когда схема её назвала; без объявления ничего не угадывается.
        if kind == "SNILS" and target == "snils" and len(digits) == 11:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:9]} {digits[9:]}"
        dictated: str | None = spoken.digits_in_words_like(digits, written)
        if dictated is not None:
            return dictated
        if _NUMERIC_FORM.fullmatch(model.strip()) and len(re.sub(r"\D", "", model)) == len(digits):
            rendered: str = _numeric_glyphs_like(written, _same_shape(model, digits))
            return value if normalize(value) == rendered else rendered
        return value
    return value


def _numeric_glyphs_like(written: str, rendered: str) -> str:
    """Keep an offset-safe spelling only where it still denotes the real digit.

    An O that denotes zero cannot be retained over a nonzero real digit: that
    would change identity. Normalization's leased mapping is the only authority
    on look-alikes; no separate typo dictionary is introduced here.
    """
    normalized: str = normalize(written)
    if len(normalized) != len(rendered):
        return rendered
    return "".join(source if source != folded and folded == target else target
                   for source, folded, target in zip(written, normalized, rendered, strict=True))


def _malformed_phone_sign(surface: str, before: str, shown_form: bool = False,
                          phone: bool = False) -> bool:
    """Whether `surface` carries a country-code sign we must not splice under.

    THREE SPELLINGS OF ONE HARM. «+8…» puts the domestic 8 under a plus. «++…»
    doubles the sign, and the second plus is not always adjacent to the digits:
    «++ 916 214-88-03» came back with the REAL digits under the doubled sign
    because the guard read only the character immediately before the run.
    An INVENTED single-digit identity («+3», «+9», «+1», «+0», «+2») is the same
    number-nobody-wrote: the splice keeps whatever stands before the last ten
    digits — right for `+7`/`8`/bare, the only identities the product approves —
    and laid the customer's REAL ten digits under a country code the agent made
    up, with an empty residual («+3 954 383-69-49» → «+3 962 056-61-63»). All
    three are the agent's own malformed string, not a form the vault may rewrite;
    the refusal leaves it standing so `surviving_substitutes` names it.

    `shown_form` says the surface is EXACTLY a form this dialogue showed the
    model. Its leading identity is the customer's own prefix mirrored at the
    mint (a customer whose number is `+1 …` is shown `+1 …`), so it is not the
    agent's invention and the verbatim seam restores it. The doubled and `+8`
    spellings are malformed whoever wrote them and are refused either way.

    `phone` says the seam has ALREADY RESOLVED this run to one of our PHONE
    rows, and only an invented leading identity needs that answer: the four
    other identities this guard clears (`+7`, `8`, bare ten, a copied form) are
    the ones the splice is right for, and eleven digits with a sign in front of
    them is also how a СНИЛС is written. Without the answer the guard refuses
    only a malformed sign — the same terms the restorer decided in.
    """
    stripped = surface.strip()
    if stripped.startswith("+8"):
        return True
    if _doubled_sign_before(stripped, before):
        return True
    return (phone and not shown_form
            and _invented_phone_prefix(stripped, before))


def _signs_before(before: str) -> int:
    """How many `+` signs stand before a run, adjacent or spaces apart.

    «++79162148803» leaves ONE plus in `before` — the run starts at the second —
    while «++ 79162148803» leaves «++ ». Counting them is what tells a doubled
    sign from a plus the sentence itself wrote («цена + 7 916…»).
    """
    tail = before.rstrip()
    signs = 0
    while tail.endswith("+"):
        signs += 1
        tail = tail[:-1].rstrip()
    return signs


def _doubled_sign_before(surface: str, before: str) -> bool:
    """Two signs before one run, whether or not the run carries one of them."""
    return _signs_before(before) + (1 if surface.startswith("+") else 0) >= 2


# One country digit and the ten subscriber digits the splice keeps — the only
# shape in which «what stands before the last ten» IS a country identity.
_PHONE_COUNTRY_DIGITS = 11


def _invented_phone_prefix(surface: str, before: str) -> bool:
    """A country identity the agent invented — refused, never re-prefixed.

    THE APPROVED SET IS `+7`, `8` AND BARE TEN, AND IT IS CLOSED. Anything else
    standing before the last ten digits is the agent's own invention, and
    splicing under it delivers a number nobody wrote: `+3 954 383-69-49` came
    back `+3 962 056-61-63` with `residual == []` — the customer's REAL
    subscriber digits under an invented country code, a fabricated E.164 number
    reaching the tool as if it were the customer's.

    `8` is refused by its own rule above (the domestic trunk under a plus) and
    needs no entry here; `7` is the one leading identity the notation approves.
    Rewriting `+3` back to `+7` is NOT the fix — the agent's explicitly written
    form survives (REMAINING-DECISIONS:16) — so the run is left exactly as
    written and the caller is told instead.

    The sign is read from the surface, or, when the surface carries none, from
    the text before it: «+ 3 …» is the same invention with a space in it, and
    «++ 9 …» carries no sign of its own at all.
    """
    stripped = surface.strip()
    digits = re.sub(r"\D", "", stripped)
    if len(digits) != _PHONE_COUNTRY_DIGITS or digits[0] in ("7", "8"):
        return False
    return stripped.startswith("+") or bool(_signs_before(before))


def _phone_in_form_of(written: str, real: str) -> str:
    """Render a known PHONE in the current sender's numeric form on either leg.

    Lookup supplies the type; canonicalization supplies content, including a
    spoken original. The literal is retained only when its normalized spelling
    already matches this render, preserving a copied homoglyph without forcing
    yesterday's grouping or spoken notation onto today's numeric argument.
    """
    normalized: str = normalize(real)
    canonical: str = canonicalize("PHONE", normalized)
    runs = spoken.numeral_runs(written)
    if len(runs) == 1 and written.strip() == written[runs[0][0]:runs[0][1]]:
        source_digits: str = spoken.run_to_digits(runs[0][2])
        target_digits: str = canonical.lstrip("+")
        if len(source_digits) == 11 and source_digits[0] in "78":
            target_digits = source_digits[0] + target_digits[-10:]
        elif len(source_digits) == 10:
            target_digits = target_digits[-10:]
        dictated: str | None = spoken.digits_in_words_like(target_digits, written)
        if dictated is not None:
            return dictated
    rendered: str = _numeric_glyphs_like(written, _digits_in_form_of(normalize(written), canonical))
    return real if normalized == rendered else rendered


def _digits_in_form_of(written: str, real: str) -> str:
    """The REAL digits in the form the AGENT wrote.

    THE FORM BELONGS TO THE AGENT, THE CONTENT TO THE VAULT — the same rule
    `in_form_of` applies to a name and an address, here for the numeric types.
    The substitute reaches the model as «+79793509887»; the model writes it
    verbatim, or as «8 979 350-98-87», or as ten bare digits, because that is
    what its schema asked for — and every one of those came back as the
    customer's ORIGINAL spelling, «8 916 402 11 87», which an E.164 parser
    refuses. Measured on the scripted agent: 54 of 54 phone arguments refused
    by the mock for `phone_not_e164` while the value inside was right.

    A phone keeps the agent's country-code convention: what stands before the
    last ten digits is the agent's, the last ten are the customer's. A date is
    rebuilt component-wise, because ISO reorders it and a positional splice
    would write «2109-19-55». Anything else with a different digit count is
    returned as the vault holds it — a splice that cannot line up is a guess.
    """
    if not _NUMERIC_FORM.fullmatch(written.strip()):
        return real
    date_written = _DATE_ANY.match(written.strip())
    date_real = _DATE_ANY.match(real.strip())
    # A DATE OF BIRTH SAID IN WORDS has no digits to splice, and the agent
    # wrote ISO: «четырнадцатое марта восемьдесят седьмого года» behind
    # «1987-01-25» came back as «1403-19-87» — the real digits laid by
    # position into the agent's layout (fresh-seed v4, derive-000/004). The
    # spoken date is read into its parts first, the same reading the vault
    # keys it by, and then rebuilt component-wise like any other.
    if date_written and not date_real:
        canonical = _date_canonical(real)
        if canonical:
            date_real = _DATE_ANY.match(canonical)
    real_digits = re.sub(r"\D", "", real)
    written_digits = re.sub(r"\D", "", written)
    if len(written_digits) < 3 or (not real_digits and not date_real):
        return real
    if date_written and date_real:
        real_first, real_middle, real_last = date_real.groups()
        if len(real_first) == 4:
            year, month, day = real_first, real_middle, real_last
        else:
            day, month, year = real_first, real_middle, real_last
        separator = re.search(r"[.\-/]", written).group()  # type: ignore[union-attr]
        if len(date_written.group(1)) == 4:
            return f"{year}{separator}{int(month):02d}{separator}{int(day):02d}"
        return f"{int(day):02d}{separator}{int(month):02d}{separator}{year}"
    # A PHONE FIRST, by the shape of the real value: eleven digits behind a 7 or
    # an 8, or a leading plus. The positional rule below would otherwise put
    # the customer's «8» under the agent's «+» and hand the tool «+8 916…».
    # The check is on the REAL value, not the written one — a twelve-digit ИНН
    # written verbatim has the same length as a phone with a prefix, and the
    # prefix rule would keep two FAKE digits of it.
    # A PHONE, BY EVIDENCE AND NOT BY A LEADING DIGIT: a plus on either side,
    # or a different count of digits with ten or more on both. «805-387-569 27»
    # is a СНИЛС that begins with an 8, and a rule that read the first digit
    # spliced a phone prefix onto it — «405-387-569 27», a checksum-valid
    # number belonging to nobody.
    plus = written.strip().startswith("+") or real.strip().startswith("+")
    counts_differ = len(written_digits) != len(real_digits)
    if (plus or counts_differ) and 10 <= len(written_digits) <= 12 and 10 <= len(real_digits) <= 12:
        return _same_shape(written, written_digits[:-10] + real_digits[-10:])
    if len(written_digits) == len(real_digits):
        return _same_shape(written, real_digits)
    return real


# One to three capitalised Cyrillic words — the shape a personal name takes in
# running text. Deliberately permissive: a false positive costs one indexed
# lookup that finds nothing, a false negative costs a fake value delivered to a
# tool as if it were real.
# ЗАГЛАВНАЯ ВЕТКА — НЕ ПОСЛАБЛЕНИЕ, А ПАРИТЕТ С ДВУМЯ ДРУГИМИ СКАНЕРАМИ.
# «КУДРЯВЦЕВ» не давал НИ ОДНОГО окна: `[а-яё]+` требует строчной буквы после
# заглавной. Ключ бы нашёлся — `name_key` и так приводит к нижнему регистру, —
# но спросить его было некому, и фамилия уходила в инструмент подменой МОЛЧА:
# `surviving_substitutes` строится на тех же окнах, поэтому и предупреждения не было.
# Латинский сканер эту форму знает (`_LATIN_WORD`, `[A-Z]{3,}` — ради «YAN
# RYBAKOV»), адресный тоже (`_PLACE_RUN_ANY_CASE`); кириллическое имя было
# единственным, кто её не знал. Три буквы — тот же порог, что у латинского, и
# по той же причине: две заглавные это инициалы или сокращение.
_NAME_WORD = re.compile(r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?|[А-ЯЁ]{3,}(?:-[А-ЯЁ]{3,})?")

# A place phrase in any case: the generic word inflects (улица/улице/улицу), the
# adjectival name agrees with it, the house number never moves. A bare settlement
# is covered by the name windows above, which already match single capitalised
# words.
# The SAME pattern the minting side uses, not a second hand-written copy of the
# same vocabulary. They were two copies and they drifted: the generator learned
# to mint «ул. Осиновая» and «Тополиный проспект» to mirror the customer's own
# wording, while this one still knew only the full words in one order — so the
# restoration window never covered the token, the lookup never ran, and a fake
# address went to the tool. Deriving it removes the possibility.
_PLACE_RUN = re.compile(LOC_TOKEN_PATTERN)
# THE SAME PATTERN, ASKED WITHOUT REGARD TO CASE, AND ONLY WHEN RESTORING.
#
# A CRM card stores «солнечная» in lower case, so the substitute agrees with it
# and the model is shown «улица ивовая 125». `place_key` casefolds and produces
# the SAME key as «улица Ивовая 125» — the key was never the problem. The
# scanner that proposes the window demanded a capital, so for lower case no
# window was ever offered and the key was never asked: the customer's real
# address never reached the tool, on the leg where personal data comes back
# from their own systems. 18 of 60 `long_order` cases on its first run.
#
# THE CAPITAL IS LOAD-BEARING IN DETECTION AND NOT HERE, and the difference is
# what the alternative is. A detector that drops it is choosing between an
# address and the whole Russian language, which is the mistake this file and
# `address.py` both carry a comment about. A RESTORER that drops it is choosing
# between an address and OUR OWN MINTED TOKENS: a window whose key is not in the
# vault resolves to nothing and costs one indexed point query, the same trade
# `_place_windows` already makes four times over for its framings.
_PLACE_RUN_ANY_CASE = re.compile(f"(?i:{LOC_TOKEN_PATTERN})")


def _place_windows(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """Framings of one address run: as matched, plus a following house number,
    plus a following «, кв. N», plus the preceding «Город, ». Deduplicated,
    longest first so the fullest framing wins the overlap resolution below.

    THE HOUSE NUMBER NEEDED ITS OWN FRAMING because the minted pattern writes it
    bare («улица Тополиная 49») and the model writes it with a marker («улица
    Тополиная, д. 49», «дом 49»). The marker is outside `LOC_TOKEN_PATTERN`, so
    the run stopped before the number, the signature lost it, and the address
    resolved to nothing — a fake street handed to the customer's tool. Extending
    the window here rather than widening the minted pattern keeps the two
    concerns apart: that pattern says what we MINT, this one says what a model
    might have WRITTEN.
    """
    candidates = {(start, end)}
    ends = [end]
    house = _HOUSE_TAIL.match(text, end)
    if house is not None:
        ends.append(house.end())
    # ХВОСТЫ ЦЕПЛЯЮТСЯ ДРУГ ЗА ДРУГА, И СПИСОК РАСТЁТ ПО ХОДУ. Здесь стоял
    # `for stop in list(ends)`: снимок списка на входе, поэтому конец, найденный
    # ВНУТРИ прохода, больше не рассматривался. Для цифровых хвостов это не
    # видно (дом и его цепочка добавляются сразу), а продиктованное «дом
    # пятьдесят семь» добавляется в проходе — и следующая за ним квартира уже не
    # искалась, окно обрывалось на доме (D7/W2). Индекс растёт по списку, а не по
    # снимку, поэтому цепочка собирается целиком.
    index = 0
    while index < len(ends):
        stop = ends[index]
        index += 1
        candidates.add((start, stop))
        # ПОДЪЕЗД — ТАКОЙ ЖЕ ХВОСТ, КАК КВАРТИРА, и стоит перед ней. Пока
        # подмена его не несла, окно о нём и не спрашивало; теперь несёт, и без
        # этой ступени окно обрывается на номере дома, ключ теряет подъезд и
        # адрес не разрешается.
        building = _BUILDING_TAIL.match(text, stop)
        if building is not None:
            candidates.add((start, building.end()))
            ends.append(building.end())
            stop = building.end()
        entrance = _ENTRANCE_TAIL.match(text, stop)
        if entrance is not None:
            candidates.add((start, entrance.end()))
            ends.append(entrance.end())
            stop = entrance.end()
        tail = _FLAT_TAIL.match(text, stop)
        if tail is not None:
            candidates.add((start, tail.end()))
            ends.append(tail.end())
            stop = tail.end()
        # …И ЧИСЛО ПЕРЕД МАРКЕРОМ — вторая основная форма того же хвоста.
        # «…, кв. 67, 5 под.» корпус пишет до квартиры, а номер подъезда —
        # ПОСЛЕ числа квартиры и ПЕРЕД словом: все три шага выше требуют
        # маркер-перед-числом, поэтому окно обрывалось на «кв. 67», ключ терял
        # подъезд, и разрешалось КОРОТКОЕ окно. Настоящее возвращалось в форму
        # подмены, у которой роли `entrance` нет вовсе, — и в инструмент уезжал
        # адрес с ФАЛЬШИВЫМ подъездом при настоящей улице (замерено на
        # PII-Bench, значение 659).
        before = _NUMBER_BEFORE_TAIL.match(text, stop)
        if before is not None:
            candidates.add((start, before.end()))
            ends.append(before.end())
        # …И ТОТ ЖЕ ХВОСТ, ПРОДИКТОВАННЫЙ ВСЛУХ (W2). Таблица выше ищет
        # `\d{1,4}`, поэтому на подмене, ОТЧЕКАНИННОЙ СЛОВАМИ («дом двадцать
        # шесть, квартира сто тридцать три»), окно обрывалось на улице: дом и
        # квартира оставались подменой, а инструмент получал смесь настоящей
        # улицы с фейковыми частями при 200. Числительное читает `spoken` —
        # тот же читатель, которым `signature_parts` складывает цифры подмены,
        # поэтому окно и ключ не могут разойтись в том, что здесь написано.
        for dictated in _dictated_tails(text, stop):
            if dictated not in ends:
                candidates.add((start, dictated))
                ends.append(dictated)
    head = _CITY_HEAD.search(text[:start])
    if head is not None and head.end() == start:
        for stop in ends:
            candidates.add((head.start(), stop))
    # …AND WITHOUT THE CITY THE RUN ITSELF BEGINS WITH. `_PLACE_RUN` matches
    # any settlement in front now (the token's city is real), so the model's
    # «Самара, улица Осиновая 79» — a public city composed around a city-less
    # token — arrives as one run, and the only framing that has a key is the
    # one that starts at the street.
    lead = _CITY_LEAD.match(text, start)
    if lead is not None and lead.end() < end:
        for stop in ends:
            candidates.add((lead.end(), stop))
    # …AND ЛЮБАЯ ВЕДУЩАЯ КЛАУЗА, А НЕ ТОЛЬКО ЗАГЛАВНАЯ. Подмена наследует
    # регистр клиента, и «сортавала, улица абрикосовая, 66», написанное
    # строчными, разбирается прогоном с ЛЮБЫМ первым словом:
    # `_PLACE_RUN_ANY_CASE` теряет `(?-i)` на имени, и «адрес сортавала» само
    # читается как город из двух слов. Ни `_CITY_HEAD`, ни `_CITY_LEAD` не
    # срабатывают (обе требуют заглавной), фрейма без ведущей клаузы не было
    # вовсе — и целая фраза не разрешалась, разрешалось окно покороче, УЛИЦА, а
    # дом оставался подменой: инструмент получал смесь настоящей улицы с
    # фальшивым домом при 200 и пустом `residual_tokens` (g08/single-005).
    #
    # ФРЕЙМ ОБЯЗАН САМ БЫТЬ УЛИЦЕЙ. Предложить любой хвост после запятой значило
    # бы объявить адресом голое «66» — и число заказчика после запятой
    # подменялось бы чужим домом.
    for comma in re.finditer(r",\s*", text[start:end]):
        low = start + comma.end()
        if not _looks_like_street_head(text, low):
            continue
        for stop in ends:
            if low < stop:
                candidates.add((low, stop))
    return sorted(candidates, key=lambda pair: pair[1] - pair[0], reverse=True)


_FLAT_TAIL = re.compile(r",?\s*(?:кв|квартир\w*|офис\w*|оф)\.?\s*\d{1,4}")
# Подъезд, как его пишет МОДЕЛЬ: «подъезд 2», «под. 2», «подъезда 2».
_ENTRANCE_TAIL = re.compile(r",?\s*(?:под[ъь]езд\w*|под)\.?\s*\d{1,4}")
# …И КАК ПИШЕТ КОРПУС: «…, кв. 67, 5 под.», «…, 12 этаж». Число СЛЕВА от
# маркера — вторая основная форма диспетчерской речи, и подмена теперь
# зеркалит её (`in_form_of`), поэтому окно восстановления обязано её знать.
_NUMBER_BEFORE_TAIL = re.compile(
    r",?\s*\d{1,3}\s*(?:\s*-\s*(?:ый|ий|ой|ая|ое|ья|й|я|е))?\s*"
    r"(?:под[ъь]езд\w*|под|этаж\w*|эт)\.?")
# Корпус/строение — такой же хвост, и стоит перед подъездом.
_BUILDING_TAIL = re.compile(r",?\s*(?:корп\w*|кор|стр|строен\w*|литер\w*)\.?\s*\d{1,4}")
# A house number as a MODEL writes it: bare, or behind «д.» / «дом» / «влад.».
# Bounded to four digits and never spanning a sentence, so it cannot swallow an
# order number that happens to follow the address.
_HOUSE_TAIL = re.compile(r",?\s*(?:(?:д|дом|вл|влад|владение)\.?\s*)?\d{1,4}"
                         r"(?:/\d{1,3})?[а-яё]?(?![\w])")


# ПРОДИКТОВАННЫЙ ЧИСЛОВОЙ ХВОСТ — маркер, за которым стоит ЧИСЛИТЕЛЬНОЕ, а не
# цифры (W2). `_HOUSE_TAIL`/`_FLAT_TAIL`/… требуют `\d{1,4}`, поэтому подмена,
# отчеканенная словами, теряла дом и квартиру: окно обрывалось на улице, дом
# оставался ФЕЙКОМ, а инструменту уезжала смесь настоящей улицы с фейковыми
# частями. Число здесь читает `spoken.numeral_runs` — тот же читатель, которым
# `signature_parts` складывает цифры подмены для ключа, — поэтому окно и ключ не
# могут разойтись в том, что написано; вторая читалка числительных разошлась бы
# с первой ровно на тех формах (склейки, опечатки из арендуемой таблицы), ради
# которых та написана.
_MARKER_TAILS = (
    # ДЛИННАЯ АЛЬТЕРНАТИВА ПЕРВОЙ: «дом» обязан съесть себя целиком, иначе
    # альтернатива «д» съедает одну букву, за маркером остаётся «ом», и это
    # слово читается как чужое — числительное за ним уже не начинается.
    re.compile(r",?\s*(?:владение|влад|дом|д|вл)\.?\s*"),
    re.compile(r",?\s*(?:строение|строен\w*|корпус\w*|корп\w*|литер\w*|стр|кор)\.?\s*"),
    re.compile(r",?\s*(?:под[ъь]езд\w*|под)\.?\s*"),
    re.compile(r",?\s*(?:квартир\w*|кв|офис\w*|оф)\.?\s*"),
)
_DICTATED_WORD = re.compile(r"[А-Яа-яЁё]+")


def _dictated_tails(text: str, position: int) -> list[int]:
    """Концы всех «маркер + продиктованное число», начинающихся в `position`.

    Возвращает СПИСОК: за одной позицией может стоять и дом, и квартира — обе
    формы нужны окну как отдельные рамки, как и у цифровых хвостов. Число
    читается `spoken.numeral_runs` (максимальный прогон числительных, склейки и
    вставки-заполнители включительно) — вторая читалка здесь разошлась бы с
    `signature_parts` ровно на тех формах, ради которых та написана."""
    out: list[int] = []
    for marker in _MARKER_TAILS:
        match = marker.match(text, position)
        if match is None:
            continue
        rest = match.end()
        word = _DICTATED_WORD.match(text, rest)
        if word is None:
            continue
        for run_start, run_stop, _words in spoken.numeral_runs(text[rest:rest + 160]):
            # Прогон обязан начинаться ПЕРВЫМ же словом: иначе между маркером
            # и числительным стоит чужое слово, и это не число этого маркера.
            if run_start != 0:
                break
            out.append(rest + run_stop)
            break
    return out
# Two words as well: the settlement is real now, and «Нижний Новгород, » is one.
_CITY_HEAD = re.compile(r"(?-i:[А-ЯЁ])[а-яё-]+(?:\s[А-ЯЁ][а-яё-]+)?,\s*$")
_CITY_LEAD = re.compile(r"(?-i:[А-ЯЁ])[а-яё-]+(?:\s[А-ЯЁ][а-яё-]+)?,\s*")
# Город в начале самой ПОДМЕНЫ — чтобы понять, назвала его модель или нет.
_STREET_TYPE_WORD = re.compile(
    r"(?i)^(?:ул\.?|улиц\w*|пр-т|пр\.?|просп\w*|пер\.?|переул\w*|б-р|бульвар\w*|ш\.?|шоссе|пл\.?|площад\w*|"
    r"наб\.?|набережн\w*|проезд\w*|тупик\w*|алле\w*|дорог\w*|тракт\w*|линия|линии)$")
_CITY_OF_TOKEN = re.compile(r"^([А-ЯЁ][а-яё-]+(?:\s[А-ЯЁ][а-яё-]+)?),\s")


def _looks_like_street_head(text: str, position: int) -> bool:
    """Начинается ли здесь улица: РОДОВОЕ слово в одном из первых двух слов.

    РОДОВОЕ, А НЕ ЛЮБОЙ МАРКЕР ЗАПИСИ. «д», «дом», «кв», «корп» — это части
    адреса, а не его тип, и фрейм, начинающийся с «д 6, кв 13», улицей не
    является. Спрошенный как улица, он разрешал СКРЕЩЕННОЕ упоминание —
    «г казань, рябиновой, д 6, кв 13», где дом одного адреса и квартира
    другого, — в настоящий адрес одной из подмен вместо отказа
    (test_location_form_adversarial F/two).

    `_STREET_TYPE_WORD` требует родовое слово ПЕРВЫМ, а подмена чеканится и
    «название первым» («Барбарисовый бульвар», «Тополиный проспект») — вторая
    форма тоже обязана считаться началом улицы, иначе фрейм, снявший ведущую
    клаузу, не предлагался бы для половины типов.
    """
    words = [word.strip(" .,") for word in text[position:position + 64].split()[:2]]
    if len(words) < 2:
        return False
    generic = [bool(_STREET_TYPE_WORD.match(word)) for word in words]
    return any(generic) and not all(generic)


def _name_windows(text: str) -> list[tuple[int, int, str]]:
    """Every contiguous 1-4 word window of capitalised Cyrillic words.

    Windows rather than maximal runs, because a sentence-initial word is
    capitalised too: `Позвоните Ивану Щукину` is one run of three, and looking
    it up whole finds nothing while `Ивану Щукину` would have matched. Misses
    are free — an indexed point query that returns no row — so enumerating is
    cheaper than being clever about which word starts a sentence.

    FOUR, NOT THREE. A two-word patronymic («Ахмед оглы») is minted as a
    four-word substitute, «Ершов Константин Мирослав Леонидович», and with a
    ceiling of three that whole token was never a window: it came back as the
    three-word tail resolved by parts plus a lone surname — and the moment a
    second person of the customer had drawn the same fake surname (36 in the
    pool, no conversation scope in a customer-wide vault), the lone «Ершов»
    had two owners, was refused, and the chimera «Ершов Рустам Ахмед оглы»
    reached the customer. One draw in ~40 on `test_product`, red on the
    merge commit of engine 0.3.16. The whole token is a window now and its
    exact key wins, as it does for every three-word name.
    """
    words = [(m.start(), m.end(), m.group()) for m in _NAME_WORD.finditer(text)]
    windows: list[tuple[int, int, str]] = []
    for i in range(len(words)):
        for size in (4, 3, 2, 1):
            if i + size > len(words):
                continue
            start, end = words[i][0], words[i + size - 1][1]
            # Only if the words are adjacent — a window may not jump a comma or
            # a lowercase word, which would join two unrelated names.
            if re.fullmatch(r"[А-ЯЁа-яё\s-]+", text[start:end]) is None:
                continue
            windows.append((start, end, text[start:end]))
    # THE DERIVED FORMS: a transliteration («Tsvetkov Vsevolod», «YAN
    # RYBAKOV») and a pair of initials («Ж.М.»). Neither is Cyrillic, so no
    # window above ever offered them, and a fake name reached the customer in
    # Latin letters with an empty residual list. Misses cost one lookup.
    latin = [(m.start(), m.end(), m.group()) for m in _LATIN_WORD.finditer(text)]
    for i in range(len(latin)):
        # The script must not truncate identity: surnames/given names and
        # patronymics need the same complete windows as Cyrillic names. A pair
        # plus an exact single-part hit can otherwise yield mixed-script output.
        for size in (4, 3, 2, 1):
            if i + size > len(latin):
                continue
            start, end = latin[i][0], latin[i + size - 1][1]
            if re.fullmatch(r"[A-Za-z\s]+", text[start:end]) is None:
                continue
            windows.append((start, end, text[start:end]))
    # ПРОГОН ЗАГЛАВНЫХ — ОДНО ИМЯ, И КОРОТКОЕ СЛОВО В НЁМ ТОЖЕ НАШЕ. Порог в
    # три буквы защищает ОДИНОЧНОЕ слово, где ошибка стоит ложной замены в
    # прозе; внутри прогона из двух-трёх слов «ЯН», «ИЯ», «ЯР» — настоящие
    # русские имена, и без них «ОСИПОВ ЯН» восстанавливалось наполовину:
    # «КИМ ЯН», настоящая фамилия рядом с ПОДМЕНОЙ имени. Та же правка, что и
    # для строчного прогона на плече аргумента, и по той же причине.
    # ДВЕ ПОДМЕНЫ, СКЛЕЕННЫЕ МОДЕЛЬЮ ЧЕРЕЗ ДЕФИС, — ЭТО ДВЕ ПОДМЕНЫ. Одному
    # человеку чеканятся два токена, когда сообщение зовёт его «Мухина», а
    # карточка — «Бирюкова»; модель пишет «Мухина-Бирюкова», целое не находится
    # ни по одному ключу, и В ИНСТРУМЕНТ УХОДЯТ ОБЕ ФАЛЬШИВЫЕ ФАМИЛИИ
    # (`residual` живого прогона 07.09, correction-019).
    #
    # ПОЛОВИНКИ ПРЕДЛАГАЮТСЯ, НО РЕШАЕТ ВОЛТ. Правило «дефис склеивает один
    # токен, и половина его не имя» — про МАСКИРОВАНИЕ, где половина
    # «Лос-Анджелеса» становилась человеком; здесь вопрос обратный, и ответ
    # даёт не морфология, а наличие строки в волте. У настоящего топонима
    # половинок в волте нет, поэтому окно просто не разрешится и ничего не
    # изменит — цена промаха ровно один индексный запрос.
    for match in re.finditer(r"(?<![А-ЯЁа-яё])([А-ЯЁ][а-яё]+)-([А-ЯЁ][а-яё]+)(?![А-ЯЁа-яё])", text):
        windows.append((match.start(1), match.end(1), match.group(1)))
        windows.append((match.start(2), match.end(2), match.group(2)))
    for run in _CAPS_RUN.finditer(text):
        words = [(m.start(), m.end()) for m in re.finditer(r"[А-ЯЁ]{2,}", run.group())]
        for i in range(len(words)):
            for size in (3, 2):
                if i + size > len(words):
                    continue
                start = run.start() + words[i][0]
                end = run.start() + words[i + size - 1][1]
                windows.append((start, end, text[start:end]))
    for m in _INITIALS_PAIR.finditer(text):
        windows.append((m.start(), m.end(), m.group()))
    # ИНИЦИАЛЫ БЕЗ ТОЧЕК — ТА ЖЕ ФОРМА, ЧТО «В. Л.», И ДРУГОГО ОКНА У НЕЁ НЕТ
    # (W4). `_NAME_WORD` требует строчных после заглавной, поэтому «Бирюков ТВ»
    # предлагалось окном из одного слова: фамилия разрешалась, а «ТВ» — подмена
    # — оставалась в тексте рядом с настоящей фамилией («Иванов ТВ»). Окно
    # покрывает пару целиком, в обоих порядках; отвечает `_derived_owner`, тем
    # же разворотом, что и для точек, — конвенция модели, а не второй ключ.
    for m in _SQUEEZED_PAIR.finditer(text):
        windows.append((m.start(), m.end(), m.group()))
    return windows


# ПАРА «ФАМИЛИЯ + СКЛЕЕННЫЕ ИНИЦИАЛЫ» (или наоборот). Две заглавные подряд —
# это инициалы без точек ровно так же, как «В. Л.» с ними; строчная после
# заглавной в паре обязана быть фамилией, иначе окно не предлагается.
# `_NAME_WORD` такие инициалы не видит вовсе (он ищет `[А-ЯЁ][а-яё-]+`), и это
# причина, по которой пара оставалась наполовину фейком.
_SQUEEZED_PAIR = re.compile(
    r"(?<![А-ЯЁа-яё])(?:[А-ЯЁ][а-яё-]+[ \t][А-ЯЁ]{2}|[А-ЯЁ]{2}[ \t][А-ЯЁ][а-яё-]+)"
    r"(?![А-ЯЁа-яё])")
# Тот же рисунок, разобранный на части, чтобы взять фамилию и инициалы по ролям.
_SQUEEZED_PAIR_PARTS = re.compile(
    r"(?:(?P<surn1>[А-ЯЁ][а-яё-]+)(?P<gap1>[ \t])(?P<ini1>[А-ЯЁ]{2})"
    r"|(?P<ini2>[А-ЯЁ]{2})(?P<gap2>[ \t])(?P<surn2>[А-ЯЁ][а-яё-]+))")


# TWO LETTERS, NOT FIVE. The floor of five (the same `names._LOWER_DICT_MIN`
# uses) guarded an ordinary short word against a wasted query — and left
# «егор», «яков», «пётр», «ян» unresolvable the day substitutes started to
# mirror the customer's lower case: a four-letter fake given name copied into
# `first_name` reached the tool as the fake. This window is offered on the
# argument leg only, and what resolves it (`Vault.residual_of`) demands a
# word that is OURS and was shown to THIS dialogue; the rest of the cost is
# an indexed query that returns nothing.
_LOWER_WORD = re.compile(r"(?<![А-ЯЁа-яё-])[а-яё]{2,}(?![А-ЯЁа-яё-])")
# ПРОГОН СТРОЧНЫХ СЛОВ — ОДНО ИМЯ, А НЕ НЕСКОЛЬКО. Одиночное окно выше знает
# только слово, и «осипов юрий» восстанавливалось пословно: «осипов» находил
# владельца и разворачивался в ПОЛНОЕ настоящее имя, а «юрий» не доставал до
# порога в пять букв и оставался ПОДМЕНОЙ — в инструмент уходило «ким юрий»,
# половина настоящего человека и половина выдуманного. «Беляев Платон» давало
# «ким викторатон». Порог в пять букв защищает ОДИНОЧНОЕ слово, где ошибка
# стоит ложной замены; прогон из двух-трёх слов на порядки специфичнее, и
# промах стоит одного индексного запроса, который ничего не находит.
# Две буквы, а не три: «Ян», «Ия», «Яр» — настоящие русские имена, и подмена
# с таким именем оставляла его фейком («ким ян»). В прогоне из двух-трёх слов
# короткое слово ничем не рискует — ключ строится по ВСЕМУ окну.
_LOWER_RUN = re.compile(r"(?<![А-ЯЁа-яё-])[а-яё]{2,}(?:[ -][а-яё]{2,}){1,2}(?![А-ЯЁа-яё-])")
# НЕОГРАНИЧЕННЫЙ СТРОЧНЫЙ ПРОГОН — для контент-плеча (W3): `_LOWER_RUN` кончается
# на третьем слове и не перекрывает находки, поэтому настоящая тройка имени в
# «клиент тихонов богдан викторович» в окна не попадала вовсе. Скользящие окна
# по этому прогону дают её и всё равно требуют ключа, который построен по ВСЕМУ
# окну, — цена промаха один индексный запрос.
_LOWER_SEQ = re.compile(r"(?<![А-ЯЁа-яё-])[а-яё]{2,}(?:[ -][а-яё]{2,})*(?![А-ЯЁа-яё-])")
# Обе половины дефисного склеивания, в любом регистре — заглавную пару
# `_name_windows` уже разбирает, строчную не разбирал никто.
_HYPHEN_PAIR = re.compile(r"(?<![А-ЯЁа-яё-])([А-ЯЁа-яё][а-яё]+)-([А-ЯЁа-яё][а-яё]+)(?![А-ЯЁа-яё-])")
_LATIN_WORD = re.compile(r"(?<![A-Za-z])(?:[A-Z][a-z]{2,}|[A-Z]{3,})(?![A-Za-z])")
_CAPS_RUN = re.compile(r"(?<![А-ЯЁа-яё-])[А-ЯЁ]{2,}(?:[ -][А-ЯЁ]{2,}){1,2}(?![А-ЯЁа-яё-])")
_INITIALS_PAIR = re.compile(r"(?<![А-ЯЁа-яё])([А-ЯЁ])\.\s?([А-ЯЁ])\.(?![А-ЯЁа-яё])")


def _tool_windows(text: str) -> list[tuple[int, int, str]]:
    """The candidate windows only a TOOL ARGUMENT is short enough to offer.

    Shared by the restoring leg and by `surviving_substitutes`, which has to look
    for exactly what the restoring leg looked for: a leftover it does not
    propose is a fake reaching the tool with an empty residual list — the
    silence this signal exists to break."""
    windows: list[tuple[int, int, str]] = []
    # A LOWER-CASE STREET STANDING ALONE IS STILL OURS, and only a tool
    # argument is short enough to ask.
    #
    # A CRM card stores «солнечная» in lower case, the substitute agrees
    # with the field, and the model writes it straight into an `address`
    # argument. `_name_windows` proposes capitalised runs only, so no
    # window was ever offered, no key was ever asked, and the fake street
    # reached the customer's tool. Seventeen of sixty `long_order` cases
    # on the family's first run.
    #
    # BOUNDED TO THE ARGUMENT LEG ON PURPOSE. Offering every long word of
    # a REPLY would put a paragraph's worth of candidates in front of the
    # vault; an argument is a field, and the same reasoning `_place_windows`
    # already uses four times over applies — a word that is not ours costs
    # one indexed point query that returns nothing, and a word that IS ours
    # is the failure this path exists to prevent.
    windows.extend((m.start(), m.end(), m.group()) for m in _LOWER_WORD.finditer(text))
    # Каждое подокно прогона, как `_name_windows` делает для заглавных:
    # начало фразы может быть чужим словом, и целиком она не найдётся.
    for run in _LOWER_RUN.finditer(text):
        words = [(m.start(), m.end()) for m in re.finditer(r"[а-яё]{2,}", run.group())]
        for i in range(len(words)):
            for size in (3, 2):
                if i + size > len(words):
                    continue
                start = run.start() + words[i][0]
                end = run.start() + words[i + size - 1][1]
                windows.append((start, end, text[start:end]))
    # ДЕФИС СКЛЕИЛ НАШУ ПОДМЕНУ С ЧУЖИМ СЛОВОМ, И ПОЛОВИНА ЕГО — НАША.
    # `_name_windows` уже предлагает обе половины, когда ОБЕ заглавные
    # («Мухина-Бирюкова», 0e877b3); строчная половина не предлагалась
    # никем — дефис стоит в классе исключения у `_LOWER_WORD` и
    # `_LOWER_RUN` намеренно, иначе разорвалась бы дефисная фамилия при
    # МАСКИРОВАНИИ. Здесь вопрос обратный: «литвина-осиновая 86» — это
    # настоящее «литвина» клиента и наша «осиновая», и без окна фейковая
    # улица уходила в инструмент. Отвечает волт, а не морфология: у
    # настоящего «Миклухо-Маклая» половинок в волте нет, окно не
    # разрешается, цена промаха — один индексный запрос.
    for match in _HYPHEN_PAIR.finditer(text):
        for half in (1, 2):
            windows.append((match.start(half), match.end(half), match.group(half)))
    return windows


def _lower_run_windows(text: str) -> list[tuple[int, int, str]]:
    """Подокна СТРОЧНОГО ПРОГОНА — «карпов юрий геннадьевич» целиком и его пары.

    ОДНА ЧИТАЛКА НА КОНТЕНТ-ПЛЕЧО (W3). На плече аргумента окно уже стояло
    (`_tool_windows`), контент-плечо его не предлагало, и модель, свернувшая
    регистр подмены (обычное дело в чате), отдавала клиенту ФЕЙКОВОЕ имя, тогда
    как тот же самый текст в аргументе разрешался (`A15` против `A14`, `D5`).

    ПРОГОН ЗДЕСЬ НЕОГРАНИЧЕН, И ЭТО НЕ УКРАШЕНИЕ. `_LOWER_RUN` — три слова, и
    `finditer` не перекрывает находки: в «клиент тихонов богдан викторович»
    первое совпадение съедает «клиент тихонов богдан», второе начинается с
    «викторович», и настоящей тройки имени среди окон НЕТ вовсе — окно в два
    слова разрешало фамилию и имя, а отчество оставалось подменой
    («иванов пётр викторович»). Поэтому по длинному строчному прогону берутся
    СКОЛЬЗЯЩИЕ окна размера 3 и 2: имя в предложении стоит где угодно.

    Одиночное строчное слово по-прежнему не предлагается: его в обычной прозе
    слишком много («вера», «надежда»), а прогон из двух-трёх слов специфичен, и
    решает всё равно волт — ключ строится по ВСЕМУ окну, и промах стоит одного
    индексного запроса, который ничего не находит."""
    windows: list[tuple[int, int, str]] = []
    for run in _LOWER_SEQ.finditer(text):
        words = [(m.start(), m.end()) for m in re.finditer(r"[а-яё]{2,}", run.group())]
        for i in range(len(words)):
            for size in (3, 2):
                if i + size > len(words):
                    continue
                start = run.start() + words[i][0]
                end = run.start() + words[i + size - 1][1]
                windows.append((start, end, text[start:end]))
    return windows


def _dictated_place_key(surface: str) -> str:
    """`place_key`, но с продиктованными числительными, прочитанными в цифры (W2).

    КЛЮЧ ПОДМЕНЫ ВСЕГДА ЦИФРОВОЙ, А ПИСЬМО БЫВАЕТ СЛОВАМИ. Подмена, отчеканенная
    на продиктованном адресе, зеркалит форму отправителя и показывается модели
    СЛОВАМИ («дом двадцать шесть»), тогда как строка волта и её `name_key` несут
    цифры. Обратный путь, который модель переписала в цифры, находил ключ
    (`A16`/`D6`), а тот же адрес, СКОПИРОВАННЫЙ дословно, — нет: `place_key`
    словесной формы состоял из числительных и с цифровым ключом не сходился, так
    что улица разрешалась, а дом и квартира оставались ФЕЙКОМ (D7/W2). Вторая
    подпись — это ровно то, чем `address_key` уже сворачивает диктовку
    (`_fold_spoken_cardinals`), и она ДОБАВЛЯЕТСЯ к обычной, а не заменяет её:
    ключ строки волта не двигается, а словесное написание приходит к нему.
    """
    tokens = re.findall(r"[А-Яа-яЁё]+|\d+", surface)
    return morph_places.match_signature(
        " ".join(morph_places._fold_cardinals(tokens)))


def _restore_inflected_candidates(text: str, vault: Vault, inflect: bool,
                                  for_tool: bool) -> list[_ResolvedSpan]:
    """NAME tokens the model put into another case no longer match their minted
    shape, so they are resolved by case-invariant key instead.

    Exactly parallel to `_restore_reformatted` for numbers, and the reason a
    fake no longer reaches a customer's tool when the model writes `Руслану
    Хвостову` instead of the nominative it was handed. Longest window first, so
    a full name wins over its own surname and half a name is never replaced.
    """
    # Names and places are gathered into ONE list before anything is resolved.
    # Doing places in a second pass let a name window claim the overlapping text
    # first, and the address was then never restored — a fake address delivered
    # to a tool, which is the failure this whole path exists to prevent.
    windows = _name_windows(text)
    if for_tool:
        windows.extend(_tool_windows(text))
    else:
        # СТРОЧНЫЙ ПРОГОН — И В ПРОЗЕ (W3). Плечо аргумента предлагало его с
        # самого начала, контент-плечо — нет, поэтому одна и та же строка
        # разрешалась в инструменте и оставалась подменой в ответе клиенту
        # (`A15` против `A14`). Одиночное строчное слово по-прежнему НЕ
        # предлагается: его в обычной прозе слишком много, а прогон из двух-трёх
        # слов специфичен, и решает всё равно волт (см. `_lower_run_windows`).
        windows.extend(_lower_run_windows(text))
    # Each window carries BOTH signatures, because a single capitalised word can
    # be either kind and the two normalisers disagree: `Еловцке` is a settlement,
    # and asking the PERSON normaliser about it returns it unchanged, so the row
    # is never found. A wrong-kind key costs one indexed lookup that misses.
    keys: dict[tuple[int, int], list[str]] = {}
    for start, end, surface in windows:
        candidates: list[str] = []
        for signature in (name_key, place_key):
            try:
                candidates.append(signature(surface))
            except Exception:  # noqa: BLE001 - morphology must never break a response
                continue
        keys[(start, end)] = candidates
    # SEVERAL CANDIDATE WINDOWS PER MATCH, not one. A single regex has to guess
    # where the address ends — before the flat, after it, with the city or
    # without — and a boundary one component off produces a different lemma
    # signature and no match at all. That guess was the last source of
    # intermittent restoration failures: each individual case looked like its own
    # bug and the pattern kept needing another special case.
    #
    # Names never had this problem because `_name_windows` enumerates instead of
    # guessing. A miss costs one indexed point query that returns nothing, so
    # offering the vault three or four framings of the same text is cheap and
    # removes the guess entirely.
    # A NAME WINDOW WITH A HOUSE NUMBER AFTER IT IS AN ADDRESS WITH THE GENERIC
    # WORD DROPPED. «Кленовая, 162» — the model shortened «улица Кленовая 162»
    # and `_PLACE_RUN` cannot see it, because every one of its alternatives needs
    # a generic word. The window is offered with a PLACE key only: a person
    # followed by a number («Иванов, 25 лет») produces a key no address token
    # has, and the miss costs one indexed query.
    place_only: set[tuple[int, int]] = set()
    for start, end, surface in list(windows):
        if " " in surface:
            continue
        for low, high in _place_windows(text, start, end):
            if (low, high) == (start, end) or (low, high) in keys:
                continue
            try:
                keys[(low, high)] = [place_key(text[low:high])]
            except Exception:  # noqa: BLE001
                continue
            windows.append((low, high, text[low:high]))
            place_only.add((low, high))

    place_framings: set[tuple[int, int]] = set()
    seen_runs: set[tuple[int, int]] = set()
    for match in (*_PLACE_RUN.finditer(text), *_PLACE_RUN_ANY_CASE.finditer(text)):
        if (match.start(), match.end()) in seen_runs:
            continue
        seen_runs.add((match.start(), match.end()))
        for start, end in _place_windows(text, match.start(), match.end()):
            surface = text[start:end]
            try:
                keys[(start, end)] = [place_key(surface), _dictated_place_key(surface)]
            except Exception:  # noqa: BLE001
                continue
            windows.append((start, end, surface))
            place_framings.add((start, end))
            place_only.add((start, end))
    if not windows:
        return []
    resolved = vault.resolve_name_keys_typed(
        {k for group in keys.values() for k in group}, for_tool)
    # NO EARLY RETURN ON AN EMPTY KEY LOOKUP. The fragment fallback below is the
    # only thing that resolves «Филипп Алексеевич», and a fragment never has a
    # key hit by construction — returning here meant the fallback could only ever
    # run for text that had already resolved by some other window.
    spans: list[_ResolvedSpan] = []
    taken: list[tuple[int, int]] = []
    # AN EXACT ADDRESS HIT OUTRANKS A WIDER FRAMING RESOLVED BY INFERENCE. The
    # settlement in a token is real now, so «Самара, улица Барбарисовая 170»
    # is one `_PLACE_RUN` match: its widest framing has no key of its own and
    # falls to the fragment fallback, which rebuilt the address from parts and
    # kept the type word the customer never wrote; the framing one step
    # shorter resolves exactly to «луговая 10». Address framings only — a
    # reordered NAME is one identity and its words resolve one by one, so for
    # names the widest window must keep winning.
    hit = {(start, end) for start, end, _ in windows
           if (start, end) in place_framings
           and any(k in resolved for k in keys.get((start, end), []))}
    for start, end, surface in sorted(windows, key=lambda w: ((w[0], w[1]) in hit, w[1] - w[0]),
                                      reverse=True):
        only_place = (start, end) in place_only
        found = next((resolved[k] for k in keys.get((start, end), [])
                      if k in resolved and (not only_place or resolved[k][0] == "LOC")), None)
        derived = (_derived_owner(surface, vault)
                   if not only_place and found is None and _is_derived_surface(surface) else None)
        bound_identity = found is not None or derived is not None
        if found is None and derived is None:
            if not only_place and _is_derived_surface(surface):
                continue
            # PART OF A SUBSTITUTE IS STILL OURS. The key above is built from the
            # whole window, so «Жуков Филипп Алексеевич» resolves and «Филипп
            # Алексеевич» — the way a Russian speaker actually addresses someone
            # — resolves to nothing, and the assistant greets the customer by an
            # invented name to their face. A service-centre persona hit exactly
            # this on live traffic.
            #
            # `residual_of` already answers «which substitute do these words
            # belong to», demands that EVERY word agree on ONE token, and was
            # built for the leak warning. Asked here it costs one indexed query
            # per unresolved window and cannot invent an owner: a name shared
            # with a real customer resolves to more than one token and is
            # refused. `name_key` is untouched — it is also called on the REAL
            # value, and widening it there would break the minting side.
            # ФРАГМЕНТ АДРЕСА РАЗРЕШАЕТСЯ И В АРГУМЕНТЕ. Раньше — только в
            # прозе: включение его для аргумента стоило 2.7 пункта, потому что
            # найденный владелец возвращался ЦЕЛИКОМ и дописывал агенту части,
            # которых в его схеме нет. Возвращает теперь `in_form_of`, по форме
            # самой строки, и цена исчезла вместе с причиной.
            #
            # Без этого схема «улица и дом, без квартиры» не работает вовсе:
            # ключ префикса не равен ключу отчеканенной подмены, владелец не
            # находится, и в инструмент уходит НАША подмена целиком.
            # A wider window offered ONLY as an address cannot be owned by
            # a NAME fragment it happens to contain. Otherwise 'Юдина на 15'
            # consumes a schedule and restores as the whole person, before the
            # genuine 'Льва Юдина' name window ever gets a chance to resolve.
            owner = ((_residual_owner(surface, vault, for_tool) if not only_place else None)
                     or _place_fragment(surface, vault, for_tool))
            if owner is None:
                continue
            # ALREADY REAL. Whole tokens were restored a step earlier, so this
            # window may be a piece of a REAL value now standing in the text;
            # a fragment that its owner's real value already contains is not
            # ours to rewrite («Валдае» inside «Валдае, улица Мира 4»).
            if surface.strip().casefold() in owner[1].casefold():
                continue
            found = owner
        if any(a < end and start < b for a, b in taken):
            continue
        if derived is None:
            entity_type, value = found
            # A LONE CITY WORD THAT THE CUSTOMER'S OWN ADDRESS CARRIES is not a
            # substitute, whatever token happens to bear the same name — see
            # `Vault.real_place_with_stem`. The whole-address window above has
            # already restored the real address when this word was part of it.
            # …in BOTH directions: a bare fake city minted for somebody else
            # before the customer named their real town (Казань's substitute
            # drew «Валдай», then «Живу на Валдае» arrived) resolves the real
            # word to the stranger's address just the same.
            if (entity_type == "LOC" and " " not in surface.strip() and not any(ch.isdigit() for ch in surface)
                    and vault.real_place_with_stem(_stem_of(surface))):
                continue
        taken.append((start, end))
        if derived is not None:
            spans.append(_ResolvedSpan(start, end, derived, "NAME", bound_identity=True))
            continue
        entity_type, value = found
        spans.append(_ResolvedSpan(start, end,
                      _in_case_of(value, surface, entity_type, inflect, vault), entity_type,
                      bound_identity=bound_identity))
    return spans


def _restore_inflected_spans(text: str, vault: Vault, inflect: bool = True,
                            for_tool: bool = False) -> list[tuple[int, int, str]]:
    return [(span.start, span.end, span.value)
            for span in _restore_inflected_candidates(text, vault, inflect, for_tool)]


def _restore_inflected(text: str, vault: Vault, inflect: bool = True,
                       for_tool: bool = False) -> str:
    return _splice(text, _restore_inflected_spans(text, vault, inflect, for_tool))


def _stem_of(word: str) -> str:
    """The invariant head of a place word, as `Vault.real_place_with_stem`
    wants it: one trailing vowel dropped («Валдае» -> «валда»)."""
    low = morph_places.to_nominative(word.strip()).lower()
    return low[:-1] if len(low) > 4 and low[-1] in "аеёиоуыэюяьй" else low


def _is_derived_surface(surface: str) -> bool:
    return bool(_LATIN_WORD.search(surface)
                or _INITIALS_PAIR.fullmatch(surface.strip())
                or _SQUEEZED_PAIR_PARTS.fullmatch(surface.strip()))


def _initials_owner(surface: str, vault: Vault) -> str | None:
    """Настоящая семья по ОДНИМ инициалам подмены — общий разворот для точечной
    и для склеенной формы (W4).

    `vault.residual_of` отвечает, чьи это инициалы: минт индексирует склеенную
    форму среди частей подмены (`translit.squeezed_initials`), и вопрос задаётся
    её же ключом. Дальше настоящее имя берётся из волта, и инициалы — от него,
    а не от подмены: иначе в тексте осталась бы половина фейка."""
    token = vault.residual_of(surface.strip())
    if token is None:
        return None
    value, entity_type = vault.reveal(token)
    if not value or entity_type != "NAME":
        return None
    shape = morph_names.name_shape(value)
    words = value.split()
    if len(shape) != len(words):
        return None
    given = next((w for w, k in zip(words, shape) if k == "name"), "")
    patronymic = next((w for w, k in zip(words, shape) if k == "patr"), "")
    if not given or not patronymic:
        return None
    # ВЕРХНИЙ РЕГИСТР, КАК У ПАРЫ С ТОЧКАМИ И БЫЛО: инициал — это буква имени, а
    # не его регистр в записи волта, и `test_derived_forms` держит «А.И.» для
    # настоящего человека, записанного строчными.
    return f"{given[0].upper()}.{patronymic[0].upper()}."


def _derived_owner(surface: str, vault: Vault) -> str | None:
    """The SAME derivation of the real name that the model applied to the fake.

    «Tsvetkov Vsevolod» is the substitute through the ICAO table; the answer is
    the real name through the ICAO table, in the same letter case. «Ж.М.» is
    the substitute's given name and patronymic abbreviated; the answer is the
    real person's, in the same punctuation. The table is found by which one
    reproduces the surface from the fake — a spelling we cannot reproduce is
    not ours to restore.

    И СКЛЕЕННАЯ ПАРА «ФАМИЛИЯ + ИНИЦИАЛЫ» (W4). «Бирюков ТВ» — та же
    аббревиатура, что «Бирюков Т.В.», только без точек. Разворот отдаёт
    НАСТОЯЩУЮ фамилию рядом с настоящими инициалами в том же порядке и в том
    же регистре: в тексте не должно остаться ни подменной фамилии, ни подменных
    инициалов — «Иванов ТВ» было именно половинчатым ответом.
    """
    pair = _SQUEEZED_PAIR_PARTS.fullmatch(surface.strip())
    if pair is not None:
        token = vault.residual_of(surface.strip())
        if token is None:
            return None
        value, entity_type = vault.reveal(token)
        if not value or entity_type != "NAME":
            return None
        shape = morph_names.name_shape(value)
        words = value.split()
        fake_shape = morph_names.name_shape(token)
        fake_words = token.split()
        if len(shape) != len(words) or len(fake_shape) != len(fake_words):
            return None
        given = next((w for w, k in zip(words, shape) if k == "name"), "")
        patronymic = next((w for w, k in zip(words, shape) if k == "patr"), "")
        surname = next((w for w, k in zip(words, shape) if k == "surn"), "")
        fake_given = next((w for w, k in zip(fake_words, fake_shape) if k == "name"), "")
        fake_patr = next((w for w, k in zip(fake_words, fake_shape) if k == "patr"), "")
        if not given or not patronymic or not surname or not fake_given or not fake_patr:
            return None
        # ПАРА ОБЯЗАНА БЫТЬ ЕГО СОБСТВЕННЫМИ ИНИЦИАЛАМИ. Одного `residual_of`
        # здесь мало: он смотрит слова длиннее двух букв, а пара инициалов — ровно
        # две, поэтому «Уваров ЩЩ» находило владельца по фамилии и ЛЮБАЯ пара
        # заглавных разворачивалась в настоящие инициалы. Гейт — тот же, что у
        # точечной формы: буквы пары равны инициалам ПОДМЕНЫ.
        written = pair.group("ini1") or pair.group("ini2")
        if written.casefold() != (fake_given[0] + fake_patr[0]).casefold():
            return None
        surname = translit.match_case(pair.group("surn1") or pair.group("surn2"),
                                      surname)
        squeezed = translit.match_case(written, f"{given[0]}{patronymic[0]}")
        if pair.group("surn1"):
            return f"{surname}{pair.group('gap1')}{squeezed}"
        return f"{squeezed}{pair.group('gap2')}{surname}"
    initials = _INITIALS_PAIR.fullmatch(surface.strip())
    if initials is not None:
        rendered = _initials_owner(initials.group(1) + initials.group(2), vault)
        if rendered is None:
            return None
        gap = " " if re.search(r"\.\s[А-ЯЁ]", surface) else ""
        return rendered.replace(".", f".{gap}", 1)
    words = surface.split()
    token = vault.residual_of(" ".join(words))
    if token is None:
        return None
    value, entity_type = vault.reveal(token)
    if not value or entity_type != "NAME":
        return None
    fake_parts, real_parts = token.split(), value.split()
    if len(fake_parts) != len(real_parts):
        return None
    # ONE CONVENTION FOR THE WHOLE NAME, READ OFF THE MODEL'S OWN WORDS. Each
    # Latin word is aligned to the fake part it spells and every letter choice
    # that alignment reveals is kept; the real parts are then rendered with
    # those choices and, for a letter the fake never contained, with the
    # measured default. Per-word table lookup stood here and wrote ICAO's
    # «iu» into «BITIUKOVA» because the fake «Шилова» could not say which
    # table the model meant — the answer was in the control arm all along.
    learned: dict[str, str] = {}
    taken: list[int] = []
    for word in words:
        found = None
        for index, fake in enumerate(fake_parts):
            if index in taken:
                continue
            mapping = translit.align(fake, word)
            if mapping is not None:
                found = index
                learned.update(mapping)
                break
        if found is None:
            return None
        taken.append(found)
    return " ".join(translit.match_case(word, translit.render(real_parts[index], learned))
                    for word, index in zip(words, taken))


def _place_fragment(surface: str, vault: Vault,
                    for_tool: bool = False) -> tuple[str, str] | None:
    """Настоящий адрес по НЕПОЛНОЙ адресной подмене, урезанный до тех же частей.

    Ключ адреса несёт все его цифры, поэтому подмена «улица Лавандовая 135,
    кв. 210», написанная моделью как «Лавандовая 135», даёт другой ключ и не
    находится. Живьём это выглядело так: в аргумент инструмента адрес пришёл
    настоящим, а в ответе клиенту агент переспросил «Да, Лавандовая 135?» —
    назвал ему выдуманную улицу как его собственную.

    Индекс частей (`place_owner`) отвечает на этот вопрос и уже стоит на разборе
    адреса по полям схемы. Правило единственного владельца прежнее: если частям
    отвечает больше одной подмены, ответа нет.

    ТОЛЬКО ДЛЯ ПРОЗЫ, И ЭТО ИЗМЕРЕНО. В аргумент модель кладёт адрес целиком, а
    разложенный по полям собирает `_join_address_fields` — там своя область
    разговора и свои роли. Тот же догадчик, включённый и на пути аргумента,
    разрешал окна, которым разрешаться было нечем, и стоил 2.7 пункта возврата:
    87.6% -> 84.9% на всём корпусе. Ровно ради такой проверки прибор и чинили
    первым.

    ВОЗВРАЩАЕТСЯ РОВНО ТО, ЧТО НАЗВАЛИ: фраза, в которую дописали
    непроизнесённую квартиру, читается как чужая.
    """
    # РОЛИ У ЦЕЛОЙ ФРАЗЫ НЕТ, И ЭТО НЕ УПУЩЕНИЕ. Сюда приходит «Лавандовая 135»
    # — улица с домом сразу, — и назвать ОДНУ роль такому куску нечем. Основа
    # улицы сама отличает адрес от адреса, поэтому голого числа здесь не
    # бывает и отсеивать по роли нечего.
    stems, numbers = morph_places.signature_parts(surface)
    if numbers and not stems:
        roles: dict[str, str] = morph_places.split_roles(surface)
        # Numeric evidence names a role, not just an owner. A house number
        # under a flat marker must never borrow the owner's real flat.
        owners: set[str | None] = {
            vault.place_owner(part, role) for role, part in roles.items()}
        if not roles or None in owners or len(owners) != 1:
            return None
        token = next(iter(owners))
    else:
        token = vault.place_owner(surface, "")
    if token is None:
        return None
    value, entity_type = vault.reveal(token, for_tool)
    if not value or entity_type != "LOC":
        return None
    if for_tool:
        # THE CITY ALONE. A `locality` field holds the substitute's city and
        # nothing else, and `in_form_of` read a lone word as a STREET — so the
        # real street went into the city field («центральная» for «Алексин»).
        # The token says which of its parts the surface is.
        fake_city = token.split(",", 1)[0].strip() if "," in token else ""
        if fake_city and surface.strip().casefold() == fake_city.casefold():
            real_city = morph_places.split_roles(value).get("city") or value.split(",", 1)[0].strip()
            return entity_type, real_city
        return entity_type, value
    fake_roles = morph_places.split_roles(token)
    lowered = surface.lower()
    keep_tail = any(fake_roles.get(role) and fake_roles[role].lower() in lowered
                    for role in ("flat", "entrance", "floor"))
    city = _CITY_OF_TOKEN.match(token)
    keep_city = city is None or city.group(1).lower() in lowered
    return entity_type, morph_places.reduce_address(value, keep_city, keep_tail)


def _residual_owner(surface: str, vault: Vault,
                    for_tool: bool = False) -> tuple[str, str] | None:
    """The (type, real value) behind a fragment of a substitute, or None.

    Only NAME substitutes have a parts index, and only a fragment of two words
    or one is worth asking about — a longer window that failed its own key is a
    different problem and guessing at it would replace text we do not own.
    """
    words = surface.split()
    if not (1 <= len(words) <= 4):
        return None
    token = vault.residual_of(surface)
    if token is None:
        return None
    value, entity_type = vault.reveal(token, for_tool)
    if not value:
        return None
    # RETURN THE MATCHING PART, NOT THE WHOLE PERSON. The model wrote «Геннадий
    # Иванович» because that is how a Russian speaker addresses someone; handing
    # back «Кузнецов Дмитрий Анатольевич» is correct but reads as a form field
    # pasted into a greeting. The substitute mirrors the real name part for part
    # — that is what `name_shape` guarantees at minting — so the same positions
    # can be taken from the real value. Only when the counts agree: if they do
    # not, the mirror does not hold and the whole value is the safe answer.
    fake_parts, real_parts = token.split(), value.split()
    if len(fake_parts) == len(real_parts):
        # СРАВНЕНИЕ ПО ИМЕНИТЕЛЬНОМУ, а не по написанному. Модель называет
        # человека в падеже фразы — «Телефон Тамары?» — и сопоставление написанного
        # не находило ни одной части, так что вместо имени в реплику
        # подставлялось ФИО целиком: «Телефон Аширбаевой Ирины Маратовны?».
        wanted = {morph_names.to_nominative(word).casefold()
                  for word in surface.split()}
        wanted |= {word.casefold() for word in surface.split()}
        # Both genders' nominatives, as `Vault.residual_of` asks: «Сорокина»
        # copied out of «Сорокина Всеволода Михайловича» is the man's genitive,
        # and with only the feminine reading the pick failed and the WHOLE
        # name went into `last_name` — refused by the parser, and wrong anyway.
        for word in surface.split():
            for gender in ("masc", "femn"):
                wanted.add(morph_names._part_to_nominative(word, gender).casefold())
        # BY ROLE WHEN THE SHAPES SAY SO, BY POSITION OTHERWISE. The token is
        # minted in the shape the detector read off the real name, and the two
        # can disagree: «миллер валерий» was read given-first, the substitute
        # came out «Владислав Сазонов», and a positional zip handed
        # `last_name` the GIVEN name «валерий». The role of the matched fake
        # word, looked up in the real name's own shape, is the right word.
        # POSITIONAL, BY CONSTRUCTION. The substitute is built slot by slot from
        # `name_shape(original)`, so fake word i stands for real word i. A pick
        # by the word's own role was tried and mapped «Мещеряков» — a surname
        # pymorphy does not know and reads as a given name — onto «артём».
        # When `last_name` still gets the given name, the SHAPE READING at mint
        # time was wrong («миллер валерий» read as given-first), and that is
        # fixed in `name_shape`, not here.
        # IN THE ORDER THE AGENT WROTE THEM. The agent copied «якушева гордея»
        # (the token shown surname-first, as the customer had written the
        # person); the real parts go back in that order, «есина рушана», not
        # in the token's own.
        picked = []
        for word in surface.split():
            forms = {word.casefold(), morph_names.to_nominative(word).casefold()}
            for gender in ("masc", "femn"):
                forms.add(morph_names._part_to_nominative(word, gender).casefold())
            for index, fake in enumerate(fake_parts):
                if (fake.casefold() in forms or morph_names.to_nominative(fake).casefold() in forms) \
                        and real_parts[index] not in picked:
                    picked.append(real_parts[index])
                    break
        if len(picked) == len(surface.split()):
            return entity_type, " ".join(picked)
    if entity_type == "NAME":
        # The part index also contains DERIVED forms such as squeezed initials.
        # A hit is an owner candidate, not proof that ordinary 'по' names the
        # person whose fake initials are ПО. Every source word must align to an
        # actual fake part here; explicit initials/transliteration use their own
        # derivation path. Falling back to the whole person invents information.
        return None
    return entity_type, value


def _in_case_of(value: str, surface: str, entity_type: str, inflect: bool,
                vault: Vault) -> str:
    """Put the real name into the case the token was standing in.

    Both readings of "restore" are legitimate and they disagree, so neither can
    be the only answer:

      * a TOOL ARGUMENT wants the person's name — `create_lead(name=...)` should
        receive «Иванов Пётр Сергеевич», not the dative the sentence happened to
        need;
      * TEXT SHOWN TO A HUMAN wants the sentence to still parse — «Позвоните
        Иванов Пётр Сергеевич» is what a machine translation reads like.

    Matching the case of what was replaced satisfies both without a mode flag:
    inside JSON the model writes the value in the nominative, so the nominative
    comes back; inside prose it writes the case the sentence needs, and the same
    case comes back.
    """
    # DISPATCH ON THE RECORDED TYPE. A place put through the person inflector is
    # read as a run of name parts, and «Санкт-Петербурге» — already in the case
    # asked for — came back «Санкт-Петербургее».
    # A TOOL ARGUMENT IS NOT A SENTENCE, so it is restored VERBATIM. The
    # paragraph above assumed the model writes the nominative inside JSON, and
    # measurement on real speech says otherwise: the substitute reaches the
    # model ALREADY inflected — `_token_for_span` puts it into the original's
    # case so the prose stays grammatical — the model copies it as written, and
    # the restorer then agrees the real value with it. «ленина пятьдесят» came
    # back from the tool as «ленина пятидесяти»: a house number in the genitive,
    # which nobody says and no CRM will match. 506 of the diverged tool calls on
    # the speech corpus are this.
    #
    # Prose still agrees; only the argument path asks for the value itself.
    if entity_type in ("LOC", "ADDR"):
        return morph_places.in_form_of(value, surface)
    if not inflect:
        # ФОРМА АДРЕСА ПРИНАДЛЕЖИТ АГЕНТУ. `inflect=False` — это плечо аргумента,
        # и здесь возвращалось наше значение целиком: продиктованный адрес
        # уезжал в CRM словами («гусева восемьдесят один квартира сто
        # семнадцать»), которые она не исполнит. Своя каноническая форма чинила
        # бы это наполовину — не ломала бы CRM, но ломала бы то, что агент
        # передавал, навязывая его схеме нашу пунктуацию.
        #
        # `in_form_of` вписывает настоящие части ВНУТРЬ строки модели: маркеры,
        # порядок и стиль числа остаются агентские. Имя так делать нельзя — у
        # него нет частей с маркерами, и `_residual_owner` уже отвечает за
        # «часть подмены».
        if entity_type in ("LOC", "ADDR"):
            return morph_places.in_form_of(value, surface)
        # A NAME IN THE AGENT'S FORM — GRAMMATICAL CASE, LETTER CASE, ORDER.
        # This branch used to hand the tool the nominative («Игорь Анфалов»
        # for an agent that wrote «Максима Дмитрова») on the reasoning that a
        # CRM wants the nominative — a guess about a tool we know nothing
        # about, and the one exception to «content from the vault, form from
        # the agent». The product's promise is to change NOTHING about how
        # the agent passes a parameter: an agent that copies the customer's
        # «есина рушана» must see «есина рушана» arrive, an agent that
        # normalises to «Есин Рушан» must see that. So the real name takes
        # the case the agent wrote the substitute in (the same reading prose
        # uses), its word order (the substitute mirrors the original part for
        # part, so positions agree) and its letter case. Letter case alone was
        # mirrored here since the 07.09 live run (262 fields); the public
        # benchmark's verbatim agent showed the other two — 78 values
        # «repaired» into a form no one had written.
        #
        # Numbers are the boundary and they stay as they are: «ленина
        # пятьдесят» once came back as «ленина пятидесяти» — a house number
        # in the genitive that no CRM matches — which is why addresses go
        # through `in_form_of` above and never through an inflector.
        return agent_form.name_cased_like(_person_in_case_of(value, surface, vault), surface)
    # ПРОЗА НИЖЕ НЕ ТРОНУТА, И ЭТО ГРАНИЦА ПРАВИЛА. Решение владельца — «никак
    # не влиять на то, как агент передаёт ПАРАМЕТРЫ»; пересказать клиенту его
    # же адрес — другой акт, и там действует уже записанное правило «клиент
    # остаётся при своих словах».
    if entity_type in ("LOC", "ADDR"):
        case = morph_places.street_case(surface)
        if case is None or case == "nomn":
            return value
        return morph_places.inflect_place(value, case)
    # …AND IN THE AGENT'S LETTER-CASE CLASS, in prose as in an argument: the
    # agent that wrote «Котов Ратмир» in its reply capitalised a name the text
    # had shown it lower-case, and its sentence keeps its capitals.
    return agent_form.name_cased_like(_person_in_case_of(value, surface, vault), surface)


def _person_in_case_of(value: str, surface: str, vault: Vault) -> str:
    """The real person in the grammatical case the agent wrote the substitute in."""
    # THE AGENT COPIED THE NOMINATIVE IT WAS SHOWN. When every word of the
    # surface is a substitute word exactly as minted, the agent bent nothing,
    # and no reading of the spelling («Карпова» — a woman's nominative or a
    # man's genitive) may bend the real name instead. Asked first because it
    # is evidence, not a prior.
    if vault.as_minted(surface):
        return value
    gender = morph_names.detect_gender(value)
    case = morph_names.detect_case(surface, gender)
    if case is None:
        return value
    # THE CASE THE CUSTOMER WROTE IN WINS A TIE. «Виктории Мещеряковой» is
    # genitive, dative and prepositional in one spelling; pymorphy3's prior
    # says genitive and «к Анне Черных» came back «к Анны Черных» — the right
    # person in a case the sentence does not take. The model kept a form
    # compatible with the original, so the original's case is the one piece
    # of evidence the surface cannot give (Б21). THE NOMINATIVE IS A CASE
    # TOO: a lone «Устинова» in a `last_name` field is the feminine
    # nominative the agent copied AND the masculine genitive the prior
    # prefers; the customer wrote «лебедева ирина петровна» in the
    # nominative, so the nominative is what the agent's spelling means here.
    written = vault.written_form(value)
    if written is not None:
        written_case = morph_names.detect_case(written, gender)
        if (written_case is not None and written_case != case
                and written_case in morph_names.cases_spelled_as(surface, gender)):
            case = written_case
    if case == "nomn":
        return value
    return morph_names.inflect_person(value, case, gender)


# Longest token across our format-preserving tokens is well under this.
_STREAM_KEEP = 64


# A run of capitalised words, or of digits and the separators that hold a number
# together. These are the shapes `_restore_inflected` slides its windows over, so
# a stream must never cut inside one.
_STREAM_RUN_RE = re.compile(
    r"[А-ЯЁA-Z][а-яёa-z]+(?:[\s,]+[А-ЯЁA-Z][а-яёa-z]+)*"
    r"|[А-ЯЁA-Z]{3,}(?:[\s,]+[А-ЯЁA-Z]{3,})*"
    r"|[\d+()][\d\s+()\-]*\d")


def _safe_cut(raw: str, cut: int) -> int:
    """Move a stream cut back so it cannot land inside a resolvable run.

    The carry withholds the last `_STREAM_KEEP` characters, which protects a
    token sitting at the END of the buffer. It does nothing for one STRADDLING
    the cut, and that is the common case: «Клиент Рыбакова Варвара Олеговна,
    адрес …» is 75 characters, so the cut fell at 11 — inside the surname — and
    «Клиент Рыба» went out while the carry began mid-word. The name was then
    resolved by neither half and the customer read the fake in the chat.

    Cutting on a word boundary is not enough either: a three-part name is three
    words, and `_restore_inflected` resolves it as ONE window. So the cut retreats
    to the start of whatever run it is standing in — after that, every run is
    wholly on one side or the other.

    Reported by a persona as «streaming loses the name when the answer also has
    an address», 3 of 3. The address made the buffer long enough for the cut to
    reach the name; with a shorter answer nothing was ever emitted before flush,
    which is why the same case passed without one.
    """
    for match in _STREAM_RUN_RE.finditer(raw):
        if match.start() < cut < match.end():
            return match.start()
    return cut


def unmask_stream_chunk(delta: str, carry: str, vault: Vault, flush: bool) -> tuple[str, str]:
    """Detokenize one streamed delta, returning (emit, new_carry).

    STATELESS by design: the caller owns the carry. A host gateway (LiteLLM) runs
    many worker processes, so keeping per-stream state inside the sidecar would
    need a shared store plus TTL cleanup for streams that die mid-flight. Handing
    the carry back to the caller — which already holds the connection — removes
    that whole class of problem.

    The carry withholds the last `_STREAM_KEEP` chars from the user until more
    arrives, so a token split across two SSE chunks is still replaced. Privacy
    note: streaming only affects the RESPONSE leg (fake -> real for the user); the
    model already received a fully-masked request, so a rare split is cosmetic,
    never a real-PII leak."""
    raw = carry + delta
    if flush:
        return unmask_text(raw, vault), ""
    if len(raw) <= _STREAM_KEEP:
        return "", raw
    cut = _safe_cut(raw, len(raw) - _STREAM_KEEP)
    if cut <= 0:
        return "", raw
    return unmask_text(raw[:cut], vault), raw[cut:]


_BARE_NUMBER_LEAF = re.compile(r"\s*\d{1,4}\s*[а-яёА-ЯЁ]?\s*")


def _bare_address_leaf(key: str, value: object) -> bool:
    """A house / flat / building / entrance / floor field holding a bare number."""
    return (isinstance(value, str) and bool(_BARE_NUMBER_LEAF.fullmatch(value))
            and morph_places.role_of_field(key) in ("house", "flat", "building", "entrance", "floor"))


def unmask_arguments(raw: str, vault: Vault,
                     leaf_notation: dict[str, str] | None = None,
                     restoration: RestorationField | None = None) -> str:
    """Detokenise a tool call's `arguments` AS JSON, not as flat text.

    THE ARGUMENTS ARE JSON AND THE REAL VALUE IS ARBITRARY TEXT. Substituting
    «ООО "АЭРОМЭП"» into a JSON string by plain replacement injects two bare
    quotes and the object stops parsing — the model gets a tool call it cannot
    read back, and the provider answers 400 on the next turn. On Russian
    business traffic that is not an edge case: every legal entity is written
    with quotes, and the same applies to a backslash or a newline in an address.

    So the string is parsed, every string LEAF is detokenised on its own, and
    the result is re-serialised — which escapes whatever the real value happens
    to contain, by construction rather than by a list of characters we
    remembered to handle.

    Masking stays flat text ON PURPOSE and the asymmetry is deliberate: the
    KEY types the VALUE there (`{"passport": "4509123456"}`), so a recogniser
    that only ever saw one value at a time would lose the evidence that types
    it. Fakes are format-preserving and carry no quotes, so flat substitution
    cannot break the JSON on the way out.

    `leaf_notation` maps a leaf KEY to the notation its tool schema declares
    (класс Ж — «snils» = XXX-XXX-XXX YY, «e164», «gost»). A leaf absent from the
    map is «not declared» and is rendered in the sender's own form, never
    guessed.

    Arguments that are not valid JSON fall back to flat text: a model is free
    to emit a broken object, and refusing to detokenise it would send a FAKE to
    the tool — the one outcome worse than imperfect text.
    """
    literals = _literals_of(vault)
    # ВЕСЬ ВЫЗОВ, А НЕ ЛИСТ: подмена, написанная агентом целиком в поле `phone`,
    # решает судьбу числа в поле `quantity` того же вызова (Б29). См.
    # `_argument_view` — почему вето читает только это плечо.
    call = _argument_view(_call_texts(raw), vault)
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return _unmask(raw, call, literals, False, True, restoration=restoration)

    notations = leaf_notation or {}

    def walk(node: object, key: str = "", path: tuple[str | int, ...] = ()) -> object:
        if isinstance(node, str):
            # VERBATIM, NOT AGREED. A tool executes on the value; grammar is a
            # property of prose. See `_in_case_of`. The leaf's schema-declared
            # notation rides as `target` and is applied only when declared.
            value = _unmask(node, call, literals, False, True, field_key=key,
                            target=notations.get(key, ""))
            if restoration is not None:
                restoration.write(path, node, value)
            return value
        if isinstance(node, list):
            return [walk(item, key, (*path, index)) for index, item in enumerate(node)]
        # A NUMBER IS A LEAF TOO, AND THE TEMPORARY-SECRET CLASS NEEDS IT.
        # `{"cvc": 314}` is an unquoted numeric field — how a customer's own
        # system serialises a short code — and this walker returned every
        # non-string unchanged, so the substitute minted for such a field
        # travelled to the tool as a FAKE with a 200 and an empty residual: the
        # one failure this file exists to prevent. Resolved by FIELD NAME (the
        # only evidence an isolated leaf has) and emitted as the SAME JSON type
        # (P02); `cvc.restore_number_leaf` refuses a real value that a JSON
        # number cannot carry (a leading zero), rather than substituting one
        # real value for another. Guarded by `key_class` inside, so no other
        # type's numeric leaf changes behaviour.
        if isinstance(node, int):
            restored = cvc.restore_number_leaf(key, node, call, for_tool=True)
            value = node if restored is None else restored
            if restoration is not None:
                restoration.write(path, node, value)
            return value
        if isinstance(node, dict):
            # Keys are the tool's own schema, not customer text — but a token
            # can only ever appear in a value, so rewriting keys would be a way
            # to break the schema and never a way to restore a value.
            # A BARE NUMBER UNDER AN ADDRESS KEY IS AN ADDRESS PART, and it is
            # answered by the join below against LOC tokens only. Restored on
            # its own first, «139» in `sflat` was found INSIDE the fake phone's
            # digits by the cross-type fragment owner and came back as the
            # customer's phone fragment «230» — a flat that is nobody's, with
            # a 200 (fresh-seed v4: 3 of 300 two-address draws).
            return {key: (value if _bare_address_leaf(key, value)
                          else walk(value, str(key), (*path, key)))
                    for key, value in node.items()}
        return node

    result = json.dumps(_join_initials_deep(
        _join_documents_deep(
            _join_addresses_deep(walk(parsed), parsed, call, literals, restoration),
            parsed, call, restoration),
        parsed, restoration), ensure_ascii=False)
    if restoration is not None:
        restoration.json(raw, result)
    return result


_COMPOSITE_KEY_RE = re.compile(r"[\s\-_.]")


def _join_documents_deep(restored: object, original: object, vault: Vault,
                         restoration: RestorationField | None = None,
                         path: tuple[str | int, ...] = ()) -> object:
    """`_join_document_fields` at EVERY level of the object, as the address join."""
    if isinstance(restored, dict) and isinstance(original, dict):
        joined = _join_document_fields(restored, original, vault, restoration, path)
        if not isinstance(joined, dict):
            return joined
        return {key: _join_documents_deep(value, original.get(key), vault,
                                          restoration, (*path, key))
                for key, value in joined.items()}
    if isinstance(restored, list) and isinstance(original, list):
        return [_join_documents_deep(value, original[index] if index < len(original) else None,
                                     vault, restoration, (*path, index))
                for index, value in enumerate(restored)]
    return restored


def _join_document_fields(restored: dict, original: dict, vault: Vault,
                          restoration: RestorationField | None = None,
                          path: tuple[str | int, ...] = ()) -> dict:
    """СОБРАТЬ ДОКУМЕНТ, РАЗЛОЖЕННЫЙ СХЕМОЙ ПО ПОЛЯМ, И РАЗЛОЖИТЬ ЕГО ОБРАТНО.

    `{"passport": {"series": "0012", "number": "345678"}}` — две подмены-листа и
    ни одного токена: каждый лист по отдельности не разрешается, потому что
    подмена у документа ОДНА. Листья спрашиваются ВМЕСТЕ, по цифровой длине
    роли из арендуемой карты частей (`ASSETS.structured.composites`), и
    настоящий документ раскладывается по тем же ролям — ровно тем же приёмом,
    каким адрес собирается из `street`/`house` (`_join_address_fields`).

    Лист переписывается ТОЛЬКО если он не разрешился сам (`restored == original`)
    и только когда собранные цифры принадлежат ОДНОЙ подмене этого разговора.
    Иначе объект остаётся как был: выдать чужой документ хуже, чем не выдать
    ничего.
    """
    if not isinstance(restored, dict) or not isinstance(original, dict):
        return restored
    for entity_type, composite in ASSETS.get().structured.composites.items():
        leaf_keys: dict[str, str] = {}
        for key in original:
            if not isinstance(original.get(key), str):
                continue
            role = composite.roles.get(_COMPOSITE_KEY_RE.sub("", key.strip().lower()))
            if role and role not in leaf_keys:
                leaf_keys[role] = key
        if any(role not in leaf_keys for role in composite.required):
            continue
        sizes = {role: composite.lengths.get(role, 0) for role in composite.order}
        parts = [original[leaf_keys[role]] for role in composite.order]
        # A LEAF OF A NUMBERED DOCUMENT CARRIES DIGITS AND ALMOST NOTHING ELSE.
        if any(not re.fullmatch(r"[\d\s\-./]*\d[\d\s\-./]*", part) for part in parts):
            continue
        digits = "".join(re.sub(r"\D", "", part) for part in parts)
        if len(digits) != sum(sizes.values()):
            continue
        real = vault.composed_document_owner(digits, entity_type)
        if not real:
            continue
        real_digits = re.sub(r"\D", "", real)
        if len(real_digits) != len(digits):
            continue
        out = dict(restored)
        offset = 0
        for role in composite.order:
            key = leaf_keys[role]
            size = sizes[role]
            part = real_digits[offset:offset + size]
            offset += size
            if out.get(key) == original[key]:
                value = _digits_like(original[key], part)
                if restoration is not None:
                    restoration.write((*path, key), out[key], value)
                out[key] = value
        return out
    return restored


_INITIALS_LEAF = re.compile(r"^\s*([А-ЯЁ])\.?(?:\s?([А-ЯЁ])\.?)?\s*$")
_NAME_LEAF = re.compile(r"^[А-ЯЁа-яё][А-ЯЁа-яё\- ]{1,60}$")


def _join_initials_deep(restored: object, original: object,
                        restoration: RestorationField | None = None,
                        path: tuple[str | int, ...] = ()) -> object:
    """`_join_initials` at every level of the object; see there."""
    if isinstance(restored, dict) and isinstance(original, dict):
        joined = _join_initials(restored, original, restoration, path)
        return {key: _join_initials_deep(value, original.get(key), restoration, (*path, key))
                for key, value in joined.items()}
    if isinstance(restored, list) and isinstance(original, list):
        return [_join_initials_deep(value, original[index] if index < len(original) else None,
                                    restoration, (*path, index))
                for index, value in enumerate(restored)]
    return restored


def _join_initials(restored: dict, original: dict,
                   restoration: RestorationField | None = None,
                   path: tuple[str | int, ...] = ()) -> dict:
    """AN INITIAL IN A TOOL CALL ABBREVIATES THE NAME WRITTEN BESIDE IT.

    A CRM schema asks for `first_name`, `middle_name` AND `initials`; the model
    fills the third from the first two. A pair («Т.О.») is a two-letter key
    the vault indexes and resolves; a SINGLE initial («С.») is one letter, which
    is nobody's key — every given name in the vault starting with С owns it —
    and it stayed the substitute's: 50 of the 56 initials the gateway arm wrote
    differently on the 05.09 medium run were single, and every one of the 55
    calls that carried initials carried `first_name` beside them. The evidence
    is not the letter, it is the OBJECT: the name the initial abbreviates was
    restored one key over in the same call, positionally, from the same fake.
    A leaf is touched only when an earlier pass left it exactly as written,
    and only when the letters match the fake name's initials — an initial that
    is not the substitute's is the customer's, and stays.
    """
    pairs: list[tuple[str, str, str]] = []   # (role hint from the key, fake word, real word)
    for key, before in original.items():
        after = restored.get(key)
        if not isinstance(before, str) or not isinstance(after, str) or before == after:
            continue
        if not _NAME_LEAF.match(before.strip()) or not _NAME_LEAF.match(after.strip()):
            continue
        fake_words, real_words = before.split(), after.split()
        if len(fake_words) != len(real_words):
            continue
        low = key.lower()
        hint = ("given" if any(mark in low for mark in ("first", "given", "имя")) else
                "patr" if any(mark in low for mark in ("middle", "patronym", "отчеств")) else
                "surn" if any(mark in low for mark in ("last", "surname", "family", "фамил")) else "")
        if len(fake_words) == 1:
            pairs.append((hint, fake_words[0], real_words[0]))
            continue
        shape = morph_names.name_shape(before.strip())
        if len(shape) != len(fake_words):
            continue
        for kind, fake, real in zip(shape, fake_words, real_words):
            pairs.append(({"name": "given", "patr": "patr", "surn": "surn"}.get(kind, ""), fake, real))
    if not pairs:
        return restored

    def letter_of(letter: str, roles: tuple[str, ...], used: set[str]) -> str | None:
        for role in roles:
            for hint, fake, real in pairs:
                if hint == role and fake not in used and fake[:1].upper() == letter:
                    used.add(fake)
                    return real[:1].upper()
        for hint, fake, real in pairs:
            if fake not in used and fake[:1].upper() == letter:
                used.add(fake)
                return real[:1].upper()
        return None

    out = dict(restored)
    for key, before in original.items():
        after = restored.get(key)
        if not isinstance(before, str) or after != before:
            continue
        found = _INITIALS_LEAF.match(before)
        if found is None:
            continue
        used: set[str] = set()
        first = letter_of(found.group(1), ("given", "patr", "surn"), used)
        if first is None:
            continue
        second = None
        if found.group(2):
            second = letter_of(found.group(2), ("patr", "surn", "given"), used)
            if second is None:
                continue
        # the same punctuation the model used, letters swapped in place
        text = before.replace(found.group(1), first, 1)
        if second is not None:
            head = text.index(first) + 1
            text = text[:head] + text[head:].replace(found.group(2), second, 1)
        if restoration is not None:
            restoration.write((*path, key), out[key], text)
        out[key] = text
    return out


def _join_addresses_deep(restored: object, original: object, vault: Vault,
                         literals: _Literals, restoration: RestorationField | None = None,
                         path: tuple[str | int, ...] = ()) -> object:
    """`_join_address_fields` at EVERY level of the object, not only the top.

    The first schema this was written against was flat — `dispatch_car` asked
    for `street`, `house`, `entrance` beside each other. A CRM's schema nests:
    `contact.address.street`. Measured on the scripted agent against a
    Yandex-shaped and an amoCRM-shaped tool: every street written into a nested
    object went to the tool as the FAKE, with a 200 and an empty residual list,
    while the same fields one level up resolved. The join is applied to each
    dict on the way down; a list is walked for the dicts inside it.
    """
    if isinstance(restored, dict) and isinstance(original, dict):
        joined = _join_address_fields(restored, original, vault, literals, restoration, path)
        if not isinstance(joined, dict):
            return joined
        return {key: _join_addresses_deep(value, original.get(key), vault, literals,
                                         restoration, (*path, key))
                for key, value in joined.items()}
    if isinstance(restored, list) and isinstance(original, list):
        return [_join_addresses_deep(value, original[index] if index < len(original) else None,
                                    vault, literals, restoration, (*path, index))
                for index, value in enumerate(restored)]
    return restored


# Имена полей, которыми схемы инструментов называют части адреса. Роль читается
# из имени, а не из формы значения: имя — это единственное, что видит и модель,
# когда решает, что куда положить.
_role_of_field = morph_places.role_of_field


def _join_address_fields(restored: object, original: object, vault: Vault,
                         literals: _Literals, restoration: RestorationField | None = None,
                         path: tuple[str | int, ...] = ()) -> object:
    """Собрать адрес, который модель разложила по ПОЛЯМ схемы, и разложить обратно.

    ПОЧЕМУ ЭТО НЕЛЬЗЯ СДЕЛАТЬ ПОЛИСТНО. Подмена адреса — одна фраза, а
    `dispatch_car` просит `street`, `house` и `entrance` порознь. Каждый лист
    JSON разбирается сам по себе, и ключ целой фразы не равен ни одному
    фрагменту по построению — сложить их было физически некому. На живом
    прогоне это 50 из 54 неразрешённых аргументов: в CRM клиента уезжала
    «улица Тополиная» и дом «49», то есть выдуманный адрес с кодом 200.

    Здесь листья, которые не разрешились сами, спрашиваются ВМЕСТЕ:
    `place_owner` ищет подмену, частями которой они являются, и требует, чтобы
    все они сошлись на ОДНОЙ — правило единственного владельца, то же самое,
    что уже держит связывание короткого упоминания на прямом пути. Настоящий
    адрес затем раскладывается по тем же ролям (`morph_places.split_roles`).

    Роль, которой у настоящего адреса нет, ОСТАЁТСЯ КАК БЫЛА. Подставить туда
    пустоту значило бы менять контракт инструмента, а подставить целую фразу —
    положить улицу в поле дома.
    """
    if not isinstance(restored, dict) or not isinstance(original, dict):
        return restored
    # EVERY address-role leaf is EVIDENCE of the owner, whether or not the leaf
    # path already resolved it; only the unresolved ones are rewritten. The two
    # were one set, and a correction («солнечная 33 кв 180 … правильно
    # солнечная 5 кв 180») broke it: inside one conversation both addresses
    # are linked to ONE fake street, so the street piece alone names two owners
    # and is refused, while the house — the piece that told them apart — had
    # been resolved a step earlier and was no longer asked.
    addressed = {
        key: value for key, value in original.items()
        if isinstance(value, str) and value.strip() and _role_of_field(key)
    }
    fragments = {key: value for key, value in addressed.items()
                 if isinstance(restored.get(key), str) and restored[key] == value}
    if not fragments:
        return restored
    # ДВА АДРЕСА В ОДНОМ ВЫЗОВЕ — ЭТО ДВЕ ГРУППЫ ПОЛЕЙ. `book_ride` просит
    # `pickup_street`/`pickup_house` и `dropoff_street`/`dropoff_house`, и,
    # спрошенные скопом, они дают ДВУХ владельцев — правило единственного
    # отказывало, и ни один из адресов не разрешался. Группа читается из
    # приставки имени поля: она и есть то, чем схема их различает.
    # ПРИСТАВКА — ЭТО ИМЯ БЕЗ СЛОВА РОЛИ, а не то, что осталось от `rsplit` по
    # нему: `address.street_type` и `streetType` — тот же адрес, что
    # `address.street` и `street`, и склеенное имя рулило ими как чужими
    # группами (см. `morph_places.field_prefix`, где токены и слова роли — один
    # источник для обеих ног).
    groups: dict[str, dict[str, str]] = {}
    for key, value in addressed.items():
        groups.setdefault(morph_places.field_prefix(key), {})[key] = value
    out = dict(restored)
    for group in groups.values():
        out = _join_one_address(out, {key: value for key, value in group.items() if key in fragments},
                                group, vault, literals, restoration, path)
    return out


def _leaf_owners(leaves: list[tuple[str, str]], vault: Vault) -> set[str]:
    """Адресные подмены, на которые указывают эти (роль, значение) листья.

    ОДИН ВОПРОС, ДВА ЧИТАТЕЛЯ ИМЁН. Схема называет роль СЛОВОМ ПОЛЯ — и
    `_role_of_field` переводит его (`building` схемы — это `house` записи, там
    лежит корпус). `split_roles` называет роль УЖЕ РОЛЬЮ, и переводить её
    второй раз нельзя: «корпус 6» под ключом `building` спрашивалось как дом 6
    и находило ЧУЖУЮ подмену с домом 6 — окно объявлялось противоречивым и
    блокировало верный адрес (`test_hard_cases`: «мончегорсуая 195 корпус 1» не
    возвращался). Поэтому переводит вызывающий, а спрашивает здесь одна
    функция.

    ЕСТЬ РАЗГОВОР — листья спрашиваются ПО ОДНОМУ, каждый своей ролью. В
    строках одного диалога адресных подмен единицы, «какая наша подмена носит
    этот дом» — осмысленный вопрос, и одинокое `{"house": "36"}` своему
    диалогу отвечает.

    НЕТ РАЗГОВОРА — листья спрашиваются ПАРАМИ, а одинокий лист не
    спрашивается вовсе (Б29). По всему волту заказчика «носит ли какая-нибудь
    наша подмена дом 7» отвечает «да» почти всегда, и на место складского дома
    заказчика молча вставал дом ЧУЖОГО НАСТОЯЩЕГО адреса. Пара «название +
    номер» спрашивает уже про АДРЕС: подмена обязана нести обе части сразу, и
    вопрос перестаёт быть утверждением о наших строках.

    ПАРАМИ, А НЕ ВСЕМИ ПОЛЯМИ РАЗОМ. У подмены нет подъезда — генератор его не
    чеканит, — поэтому в `entrance` модель кладёт выдуманное число, у которого
    владельца нет вовсе, и один такой лист отказом за всю группу не позволял
    разрешить ничего. Пара, в которую он попал, молчит; пара «улица + дом»
    отвечает.

    В ПАРЕ ОБЯЗАНО БЫТЬ НАЗВАНИЕ. Два голых числа — это две догадки, а не
    свидетельство: «дом 6» и «квартира 154» вместе назовут любую подмену, у
    которой сошлись обе цифры, и ни одна из них не сказала, о какой улице речь.
    """
    if vault.fragment_scope_is_a_dialogue():
        named = {vault.place_owner(value, role) for role, value in leaves}
        named.discard(None)
        return named
    values = [value for _role, value in leaves]
    paired: set[str] = set()
    for first in range(len(values)):
        for second in range(first + 1, len(values)):
            pair = (values[first], values[second])
            if not any(morph_places.signature_parts(value)[0] for value in pair):
                continue
            # РОЛЬ ПАРЫ НЕ НАЗЫВАЕТСЯ, И ЭТО НЕ УПУЩЕНИЕ: у пары «название +
            # номер» роль не одна, а основа улицы сама отличает адрес от
            # адреса — отсеивать по роли здесь нечего (`place_owner`).
            token = vault.place_owner(f"{pair[0]} {pair[1]}", "")
            if token is not None:
                paired.add(token)
    if len(paired) > 1:
        # ОДНО ЯДРО С РАЗНЫМИ ЧАСТЯМИ — ЭТО НЕ ДВА ВЛАДЕЛЬЦА (D-081/W8). Ядро
        # дома и выросшие на нём строки (квартира 7, квартира 42, корпус 2) —
        # одно место, и пара «улица + дом» законно отвечает ДРУГОЙ строкой, чем
        # пара «улица + квартира 42»: адрес объявлялся противоречивым, и целое
        # настоящее написание оставалось подменой (а поле схемы — фейком).
        # Вопрос о ЦЕЛОМ различает их: на него отвечает только строка, несущая
        # ВСЕ названные части, и тогда владелец снова один. Два настоящих разных
        # адреса по-прежнему не сходятся ни на одной строке и остаются отказом.
        whole = vault.place_owner_of_whole(tuple(leaves))
        if whole is not None:
            return {whole}
    return paired


def _address_owners(evidence: dict[str, str], vault: Vault) -> set[str]:
    """`_leaf_owners` для СХЕМЫ: ключ — ИМЯ ПОЛЯ, роль читается из него."""
    return _leaf_owners([(_role_of_field(key), value) for key, value in evidence.items()],
                        vault)


def _role_owners(roles: dict[str, str], vault: Vault) -> set[str]:
    """`_leaf_owners` для РАЗОБРАННОЙ ФРАЗЫ: ключ УЖЕ РОЛЬ (см. `_leaf_owners`)."""
    return _leaf_owners(list(roles.items()), vault)


def _join_one_address(restored: dict[str, object], fragments: dict[str, str],
                      evidence: dict[str, str], vault: Vault,
                      literals: _Literals, restoration: RestorationField | None = None,
                      path: tuple[str | int, ...] = ()) -> dict[str, object]:
    """Одна группа полей — один адрес. `evidence` — все адресные листья группы
    как их написала модель, `fragments` — те из них, что ещё не разрешились."""
    if not fragments:
        return restored
    # КАЖДОЕ ПОЛЕ ГОЛОСУЕТ ОТДЕЛЬНО, И НЕ КАЖДОЕ ГОЛОСУЕТ. У подмены нет
    # подъезда — генератор его не чеканит, — поэтому в `entrance` модель кладёт
    # выдуманное число, у которого владельца нет вовсе. Спросив все поля разом,
    # мы получали бы отказ из-за одного такого поля и не разрешали ничего.
    # Поле без владельца просто молчит и остаётся как было; поля с владельцем
    # обязаны сойтись на ОДНОЙ подмене.
    # КАЖДЫЙ ЛИСТ СПРАШИВАЕТСЯ СВОЕЙ РОЛЬЮ — той, которую назвала схема (Б29).
    # Голое «41» под ключом `house` без роли находило любую подмену, у которой
    # 41 стоит хоть где: складской дом заказчика молча уезжал в CRM номером
    # чужого настоящего дома. Имя поля — единственное, что видит и модель,
    # решая, что куда положить, поэтому оно же и спрашивает. А ЗА ПРЕДЕЛАМИ
    # ДИАЛОГА роли мало и листья спрашиваются парами — см. `_address_owners`.
    owners = _address_owners(evidence, vault)
    if not owners:
        # NO LEAF WITH A NUMBER NAMED AN OWNER — a `street` field alone, on a
        # street this conversation faked twice (a corrected house). The street
        # is one answer whichever row is asked; the vault says so only when
        # every owner agrees on the real street.
        owners = {vault.place_owner_by_street(value) for value in evidence.values()}
        owners.discard(None)
    if not owners:
        # НИ ОДИН ЛИСТ НЕ НАЗВАЛ ВЛАДЕЛЬЦА — но, может быть, они вместе назвали
        # подмену ЦЕЛИКОМ (Б29). Каждый лист поодиночке ищется как кусок, то
        # есть в своём разговоре; у обратного прокси разговор выведен из
        # транскрипта и никогда не равен тому, в котором подмена отчеканена,
        # поэтому целый адрес, разложенный по полям схемы, пропадал молча.
        # Занятая КАЖДАЯ роль подмены — это уже не кусок, и спрашивается она
        # как целое. Спрашивается ПОСЛЕ листов, а не вместо них: внутри своего
        # разговора листы отвечают и на неполный набор ролей.
        whole = vault.place_owner_of_whole(tuple(
            (_role_of_field(key), value) for key, value in evidence.items()))
        if whole is not None:
            owners = {whole}
    if len(owners) != 1:
        return restored
    owner = owners.pop()
    value, entity_type = vault.reveal(owner)
    if not value or entity_type != "LOC":
        return restored
    roles = morph_places.split_roles(value)
    # THE TOKEN KNOWS WHETHER THERE IS A CITY. The role splitter reads the real
    # value by shape and a lower-case spoken «воткинск школьная двенадцать»
    # carries no capital and no comma to split on — but the substitute was
    # minted WITH a city («Тверь, улица …»), which the detector decided at
    # mint time, so the head's first word is the settlement.
    if "city" not in roles and _CITY_OF_TOKEN.match(owner) and roles.get("street"):
        head = roles["street"].split()
        if len(head) >= 2:
            roles["city"] = head[0].strip(" ,.")
            roles["street"] = " ".join(head[1:])
    elif "city" not in roles and roles.get("street"):
        # NO CITY IN THE TOKEN EITHER — the detector saw none at mint time —
        # yet the head is two lower-case words: «воткинск школьная». The ГАР
        # register decides: the second word names a street and the first does
        # not, so the first is the settlement. Both conditions, or «большая
        # садовая» would lose its first word.
        head = roles["street"].split()
        if len(head) >= 3 and not _STREET_TYPE_WORD.match(head[0]) and _STREET_TYPE_WORD.match(head[1]):
            # «ижевск проезд ленина»: the type word marks where the street
            # begins, so the word before it is the settlement.
            roles["city"] = head[0].strip(" ,.")
            roles["street"] = " ".join(head[1:])
        elif len(head) == 2 and not _STREET_TYPE_WORD.match(head[0]) and not _STREET_TYPE_WORD.match(head[1]):
            from pseudex import address as address_mod
            from pseudex.assets import ASSETS
            register = ASSETS.get().address if ASSETS.is_loaded else None
            if (register is not None and address_mod._gar_reaches(head[1], register)
                    and not address_mod._gar_reaches(head[0], register)):
                roles["city"] = head[0].strip(" ,.")
                roles["street"] = head[1]
    out = dict(restored)
    spellings = _spellings_for(value, literals.as_written)
    # ОДНА УЛИЦА НА ДВА ЛИСТА — РОВНО ОДИН РАЗ. Схема, которая спрашивает
    # `street` И `street_type` порознь (`streetType` — то же имя), называет одну
    # улицу двумя полями: имя в одно, родовое слово в другое. Тогда в поле
    # `street` едет ИМЯ (тип у него есть свой лист), иначе тип уезжает в
    # инструмент дважды — и в улице, и рядом. Схема без листа типа получает
    # улицу ЦЕЛИКОМ, как и получала.
    split_street_type = any(_role_of_field(key) == "street_type" for key in evidence)
    for key in fragments:
        role = _role_of_field(key)
        part = roles.get(role)
        if role == "street" and split_street_type:
            part = roles.get("street_name") or part
        if part:
            # THE FORM IS THE AGENT'S: digits where it wrote digits, no type
            # word where it wrote none, and the AGENT'S LETTER-CASE. The vault
            # keeps the street as the customer wrote it («мончегорской»,
            # lower); the agent copied a capitalised fake into the field
            # («Вязовая»), so the real word goes back capitalised too —
            # «Мончегорской». `part_in_form_of` handles markers and digits,
            # `cased_like` the case, word for word. See `agent_form`.
            laid = morph_places.part_in_form_of(fragments[key], part, role)
            # AND THE CUSTOMER'S OWN SPELLING OF THE WORD. This leg never
            # passes through `unmask_text`'s splice — it reads the whole
            # address out of the vault and cuts it into the schema's fields —
            # so the re-spelling that puts back a look-alike letter has to be
            # asked for here too. See `_as_written_rows`.
            #
            # ASKED OF THE WHOLE ADDRESS, APPLIED TO THE PIECE. The value is in
            # hand here (`vault.reveal(owner)`), so the row that speaks is the
            # one that IS this address — a field on its own carries neither its
            # neighbours' words nor its own house number, and could never
            # recognise itself.
            value = _as_written(agent_form.cased_like(laid, fragments[key]), spellings)
            if restoration is not None:
                restoration.write((*path, key), out[key], value)
            out[key] = value
    return out


def _shown_surfaces(text: str, forms: list[tuple[str, str, str]]) -> set[str]:
    """Shown views are evidence even when they are not whole minted tokens."""
    found: set[str] = set()
    for shown, _, _kind in forms:
        if not shown:
            continue
        for match in re.finditer(re.escape(shown), text):
            low, high = match.span()
            if low and text[low - 1].isalnum() and shown[0].isalnum():
                continue
            if high < len(text) and text[high].isalnum() and shown[-1].isalnum():
                continue
            found.add(shown)
            break
    return found


def _refused_sign_runs(text: str, vault: Vault) -> set[str]:
    """The runs the restoring leg REFUSED under a broken or invented sign.

    A REFUSAL NOBODY CAN SEE IS THE SILENCE THIS FUNCTION ENDS. The orphan the
    ordinary residual sources cannot name is a phone wearing a country identity
    the vault never wrote: «+3 9241051107» is not a token surface and not a
    fragment of one — its identity is the LAST TEN digits — so the exact-token
    question, `residual_of` and `digit_fragment_is_ours` all miss it, and the
    answer goes out with `residual == []` while a fabricated E.164 number stands
    where the customer's own value belongs (P12, M04: an unknown is not a
    success).

    THE QUESTION IS THE RESTORER'S OWN, ASKED AGAIN. The refusal is recognised
    by the same guard that made it, with the same three answers the seam had in
    hand — the run, the text before it, and whether the vault resolved it to a
    PHONE — and the claim «this is ours» by the same signature question the
    restorer asked. So a number of the customer's own is never named and a
    substitute that resolved (and is therefore no longer standing) is not
    reported by the caller.

    THE SIGN IS PART OF THE RUN. «++ 9…» leaves the doubled sign outside the
    `_NUM_RUN` match, and naming the bare ten would hide the very defect the
    caller has to see; the return extends the run backwards over the signs, with
    the leading whitespace trimmed so the reported string is findable in the
    answer.
    """
    runs: list[tuple[int, int, int, str]] = []
    for match in _NUM_RUN.finditer(text):
        end = match.end()
        raw = text[match.start():end]
        # THE TWO SHAPES THAT COULD HAVE BEEN REFUSED, WITHOUT THE VAULT: a
        # malformed sign, or an invented identity (which the seam refused only
        # because it resolved this run to a phone). Anything else was not refused
        # and is not asked about — the ordinary answer here is that nothing is.
        if not (_malformed_phone_sign(raw, text[:match.start()])
                or _invented_phone_prefix(raw, text[:match.start()])):
            continue
        digits = re.sub(r"\D", "", raw)
        if not digits:
            continue
        start, probe = match.start(), match.start()
        while probe > 0 and (text[probe - 1] == "+" or text[probe - 1].isspace()):
            probe -= 1
        if "+" in text[probe:start]:
            while probe < start and text[probe].isspace():
                probe += 1
            start = probe
        runs.append((match.start(), start, end, digits))
    if not runs:
        return set()
    asked: set[str] = {digits for _at, _low, _high, digits in runs}
    asked |= {digits[-10:] for digits in asked if len(digits) >= 10}
    owners = vault.resolve_digit_signatures_typed(asked, True)
    refused: set[str] = set()
    for at, low, high, digits in runs:
        hit = owners.get(digits) or owners.get(digits[-10:], ("", ""))
        # ASKED WITH THE PHONE FLAG, BECAUSE THE SEAM HAD IT: a run that resolves
        # to a СНИЛС was never refused for an invented identity, and naming it
        # here would report a refusal that did not happen.
        if _malformed_phone_sign(text[at:high], text[:at], phone=hit[0] == "PHONE"):
            refused.add(text[low:high])
    return refused


def _extended_phone_runs(text: str, vault: Vault) -> set[str]:
    """A known PHONE signature plus one adjacent digit, without a real-value splice."""
    candidates: list[tuple[str, set[str]]] = []
    for match in _NUM_RUN.finditer(text):
        surface = match.group().strip()
        digits = re.sub(r"\D", "", surface)
        # A phone minted here carries eleven digits, so a run of twelve is that
        # phone plus ONE agent-added digit — and the added digit may sit BEFORE,
        # AFTER or INSIDE it. The old suffix-only probe `digits[1:11]` saw only
        # the tail, so a prefix or interior insertion was read as an unknown
        # number and the restore path spliced a real value under the spurious
        # digit while this detector stayed silent. Deleting each position once
        # yields every eleven-digit remainder the model could have written; each
        # remainder's ten-digit tail is the same number in its domestic shape
        # («8 (979) 555-33-221» minus its suffix is «89795553322», whose tail is
        # the minted last-ten).
        if len(digits) != 12:
            continue
        signatures: set[str] = set()
        for i in range(len(digits)):
            window = digits[:i] + digits[i + 1:]
            signatures.add(window)
            signatures.add(window[-10:])
        candidates.append((surface, signatures))
    owners = vault.resolve_digit_signatures_typed(
        {signature for _surface, signatures in candidates for signature in signatures}, True)
    return {surface for surface, signatures in candidates
            if any(signature in owners and owners[signature][0] == "PHONE"
                   for signature in signatures)}


def residual_tokens(text: str, vault: Vault) -> list[str]:
    """Minted tokens still standing in text that has already been detokenized.

    THE SIGNAL EVERY PERSONA ASKED FOR, in the same words three times: «мне
    хватило бы заголовка X-Pseudex-Residual». When the model reorders a name,
    shortens it, or reformats a plate, the restored form no longer matches and
    the FAKE goes to the customer's tool — with a 200, empty counters and nothing
    in the log. Their code cannot find out, so they cannot fail closed on their
    own side.

    TWO ARGUMENTS, AND THEY STAY TWO. This is a public function with a caller
    outside the engine — `bench/agentpii4/gateway.py`, the arm the benchmark
    compares against and which we do not edit. It was briefly given four
    parameters and that arm died on every tool call. A published shape does not
    change; the leg-aware check that needs the agent's own text and the leg it
    came from is `surviving_substitutes`, and it has its own name for exactly
    that reason.

    Read-only and cheap: the candidates are the same shapes `unmask_text` already
    scans for, and each is one indexed lookup that MISSES for a real value and
    HITS for a substitute we minted. A hit here means one thing only — this
    string is ours, and it should not have survived.
    """
    forms: list[tuple[str, str, str]] = vault.shown_forms()
    spoken_residual: set[str] = {text[hit.start:hit.end]
                                for hit in _spoken_identifier_hits(text, vault, False)}
    shown_residual: set[str] = _shown_surfaces(text, forms)
    extended_phone: set[str] = _extended_phone_runs(text, vault)
    candidates = {match.group() for match in token_re().finditer(text)} | spoken_residual | shown_residual
    # The v6 finance family's shapes too: a free-form token can begin after a cue
    # word whose tail looks like a plate, and the non-overlapping scan of
    # `token_re` then never sees it (see `_written_candidates`).
    candidates |= {match.group()
                   for match in ru_pii_v6.FINANCE_TOKEN_RE.finditer(text)}
    # The v6 utility/account/education/travel family's shapes too, for the same
    # reason: a login, a pass number or a CRM id is not a shape any earlier family
    # claims, and a leftover substitute that is never a candidate is never named.
    candidates |= {match.group()
                   for match in ru_pii_v6.UTILITY_TOKEN_RE.finditer(text)}
    # A PHONE TOKEN IS WRITTEN THE CUSTOMER'S WAY (vault `_digits_in_customer_
    # form`), so `TOKEN_RE`'s «+79…» shape no longer names it; every digit run
    # is offered and the vault answers by signature.
    candidates |= {match.group().strip() for match in _NUM_RUN.finditer(text)}
    # A NAME the model REWROTE no longer matches any token, so `TOKEN_RE` alone
    # would miss exactly the case this exists for. Capitalised runs are offered
    # too, and the vault decides which of them are made of its own words.
    candidates |= {surface for _start, _end, surface in _name_windows(text)}
    if not candidates:
        return []
    # THE SURFACE THE VETO KEPT, NAMED. `_shown_surfaces` finds only the EXACT
    # copy of a shown form; a rewritten surface is a different string, so
    # `unmask_text` refuses it by IDENTITY and the caller has to be told the
    # same way — a refusal nobody can see is the silence this function ends.
    conflicts: dict[str, frozenset[str]] = _conflict_keys(forms)
    unresolved: set[str] = {value for value in candidates
                            if _conflicts_with(value, conflicts)}
    known = vault.detokenize_many(candidates)
    residual = ({value for value in candidates if value in known}
                | spoken_residual | shown_residual | unresolved | extended_phone)
    residual |= {value for value in candidates
                 if value not in known and vault.residual_of(value) is not None}
    return _maximal(residual)


def surviving_substitutes(written: str, restored: str, vault: Vault,
                          for_tool: bool) -> list[str]:
    """Our substitutes the agent wrote that are STILL STANDING after restoration.

    ONE RULE INSTEAD OF SEVEN QUESTIONS ABOUT SHAPE (known-issues Б28ter):

        a residual is a substitute THIS RUN MINTED and that is still standing
        in the output. Nothing else is called a residual.

    What that replaced was a row of questions about the SHAPE of the value —
    «does any substitute wear this number anywhere», «do these digits sit inside
    anybody's digits» — each of them an attempt to work out whether a string was
    ours by looking at it. The vault knows, and it knows in the same terms the
    restoring leg used: the ROLE a field or a cue named, the TYPE and the SIDE a
    cue named. A question the restore never asked reports a refusal that never
    happened: a `flat` number answered by a substitute's HOUSE was 10 of the 21
    false alarms a 152-case sweep found, on values the gateway had never touched.

    ONE PLACE WHERE THE VAULT CANNOT KNOW, STATED HERE RATHER THAN HIDDEN. A
    bare number under an address role, with no conversation named and no street
    beside it, is two digits: when several of this customer's substitutes carry
    that house, the vault cannot tell one of them from a number of the
    customer's own, and neither can the restoring leg — which is exactly why it
    refused. This reports it, because a possible fake in a tool call is worth a
    second look and silence is not. `conversation_id` removes the ambiguity on
    both legs at once (measured: every class resolves, nothing is reported).

    TWO TEXTS, AND THE ORDER OF THE TWO QUESTIONS IS PART OF THE RULE. Asked of
    the RESTORED text alone this could not tell a leftover fake from a real
    value that happens to look like one: a customer's own street sharing a stem
    with two of our substitutes, a real «Анна» whose name is a word of somebody
    else's fake. Both answered «ours» and both were reported — 5 false alarms in
    50 dialogues, on CORRECT restorations. So the candidates come from what the
    AGENT WROTE, and a candidate is reported only if it is still there
    afterwards: a substitute that resolved is gone from the answer by
    construction, and a real value is never in the question.

    THAT ORDER IS ALSO WHAT MAKES THE VAULT'S PART CHEAP. The «still standing»
    test is string work over text already in hand, so the vault is asked only
    about the few candidates that survived — on an answer where everything
    resolved, which is the ordinary one, it is asked nothing at all.

    A FRAGMENT REFUSES WHATEVER ITS TYPE, AND ON WHATEVER LEG. A street with no
    number, a house number with no street, a date the agent renotated, four
    digits cut out of a phone — each is resolved by its own lookup, and each of
    those lookups answers only when the candidate is unambiguous. Silence means
    the substitute stays, so it is the same event four times over, and it has to
    be named on the PROSE leg as loudly as in an argument: «Дом 47.» lost 22 of
    50 house numbers without a word while the same field in a tool call was
    reported.

    `for_tool` OFFERS THE SAME WINDOWS THE RESTORING LEG OFFERED. A leftover
    this does not propose cannot be reported, and a lower-case street standing
    alone in a schema field is exactly the shape that leaks; in prose those
    windows would put a paragraph of words in front of the vault, which is why
    the restoring leg bounds them the same way (`_tool_windows`).

    THE ONE LEFTOVER THAT WEARS A SURFACE OF THE AGENT'S OWN MAKING is a
    substitute under a refused country sign («+3 <our ten digits>»): it is ours
    by its digits and has no minted surface, so the sources above cannot see it
    and `_refused_sign_runs` names it — still «a substitute this run minted and
    that is still standing», read by the question the restorer asked.
    """
    forms: list[tuple[str, str, str]] = vault.shown_forms()
    shown_residual: set[str] = {
        shown for shown in _shown_surfaces(written, forms)
        if _still_standing(shown, restored)}
    extended_phone: set[str] = {
        surface for surface in _extended_phone_runs(written, vault)
        if _still_standing(surface, restored)}
    # A REFUSED COUNTRY SIGN IS A RESIDUAL TOO, AND NOTHING ELSE NAMES IT. A
    # substitute the agent prefixed with an invented identity keeps OUR digits
    # and wears a surface the vault has no row for, so every other source here
    # answers «not ours» about it (see `_refused_sign_runs`).
    refused_sign: set[str] = {
        surface for surface in _refused_sign_runs(written, vault)
        if _still_standing(surface, restored)}
    asked = _written_candidates(written, for_tool).standing_in(restored)
    # THE REWRITTEN SURFACE THE VETO REFUSED IS A RESIDUAL TOO. It is not a
    # substring of any shown form, so `_shown_surfaces` cannot see it, and the
    # vault has no minted row to answer for it (`detokenize_many` misses) — the
    # one question that names it is the identity question the restorer asked.
    conflicts: dict[str, frozenset[str]] = _conflict_keys(forms)
    unresolved: set[str] = {value for value in asked.named | asked.words
                            if _conflicts_with(value, conflicts)}
    # ТОТ ЖЕ ВЫЗОВ И ТО ЖЕ ПЛЕЧО, ЧТО ВИДЕЛО ВОССТАНОВЛЕНИЕ (Б29). Вид выбирается
    # по плечу, а не берётся один на оба: вето читает только аргумент
    # (`_argument_view`), и сигнал, спросивший о прозе с вето, доложил бы об
    # отказе, которого на этом плече не было.
    call = (_argument_view if for_tool else _call_view)(_call_texts(written), vault)
    # ЧИСЛО АДРЕСА, КОТОРОЕ ВОССТАНОВЛЕНИЕ ПЫТАЛОСЬ И НЕ СМОГЛО ОТОБРАЗИТЬ. Это
    # не «ещё одна догадка по форме»: вопрос задаётся подмене, чья УЛИЦА стоит в
    # том же прогоне, и она отвечает своими частями. Смесь «настоящая улица +
    # фальшивый дом» уходила в инструмент с 200 и пустым `residual_tokens`
    # (g08/single-005) — здесь она перестаёт быть молчаливой.
    leftovers = _address_numbers_left(written, restored, call)
    if not asked.any():
        return _maximal(shown_residual | unresolved | extended_phone | refused_sign | leftovers)
    known = call.detokenize_many(asked.named)
    residual = ({value for value in asked.named if value in known}
                | shown_residual | unresolved | extended_phone | refused_sign)
    residual |= {value for value in asked.named
                 if value not in known and call.residual_of(value) is not None}
    residual |= _pieces_of_ours(asked, residual, call)
    residual |= leftovers
    residual |= {written[hit.start:hit.end]
                 for hit in _spoken_identifier_hits(written, call, for_tool)
                 if written[hit.start:hit.end] in asked.named}
    return _maximal(residual)


def _maximal(residual: set[str]) -> list[str]:
    """MAXIMAL WINDOWS ONLY. «Римма Цветкова» is one leftover, not three; a
    caller reading a count would otherwise see the same defect three times and
    could not tell one damaged name from several."""
    return sorted(value for value in residual
                  if not any(value != other and value in other
                             for other in residual))


def _address_numbers_left(written: str, restored: str, vault: Vault) -> set[str]:
    """Числовой компонент адресного прогона, который ОСТАЛСЯ подменой.

    ПОЧЕМУ ЭТО ОТДЕЛЬНЫЙ ВОПРОС. Все прочие вопросы сигнала — про ФОРМУ
    строки: цифровой прогон в семь знаков, целое значение в три цифры, слово
    улицы, подсказка перед числом. Дом в две цифры не проходит ни один из них,
    и отказ восстановления по нему молчал (g08/single-005: «дом 22 остался
    подстановкой, `residual {}`»). Здесь спрашивает не форма, а ПОДМЕНА: улица
    прогона называет владельца, и владелец отвечает, его ли это дом, квартира,
    корпус или подъезд.

    ЧУЖОЕ ЧИСЛО В ВОПРОС НЕ ПОПАДАЕТ. Совпадение проверяется по РОЛИ и по
    `house_digits` — читалке числительных, которой пользуются и ключ, и чеканка,
    — а не по длине и не по «похоже на дом». Число, которого нет ни у одной
    нашей подмены этой улицы, не называется: молчание о чужом числе — это не
    молчание об отказе.

    СПРАШИВАЕТСЯ ТОЛЬКО ТО, ЧТО СТОИТ В ВОССТАНОВЛЕННОМ ТЕКСТЕ. Подмена,
    которую восстановление отобразило, из вопроса уходит: сообщить о ней значило
    бы поднять тревогу на верном ответе.
    """
    out: set[str] = set()
    for match in _PLACE_RUN_ANY_CASE.finditer(written):
        for start, end in _place_windows(written, match.start(), match.end()):
            surface = written[start:end]
            roles = morph_places.split_roles(surface)
            street = roles.get("street", "").strip()
            if not street:
                continue
            numbers = {role: value for role, value in roles.items()
                       if role in ("house", "flat", "building", "entrance")
                       and value and _still_standing(value, restored)}
            if not numbers:
                continue
            token = (vault.place_owner(street, "street")
                     or vault.place_owner_by_street(street))
            if token is None:
                continue
            whole = morph_places.split_roles(token)
            for role, value in numbers.items():
                owned = whole.get(role, "")
                if (owned and morph_places.house_digits(owned)
                        == morph_places.house_digits(value)):
                    out.add(value)
    return out


class _Candidates(NamedTuple):
    """What the restoring leg offered the vault about one text, by QUESTION.

    Four groups because four different questions are asked, and giving one
    group's strings to another question is how this gets slow or noisy.

    `named` is what may be a whole substitute: the vault is asked to recognise
    it (`detokenize_many`, `residual_of`) and, failing that, to say whether it
    is a fragment of one. `words` are the extra windows only a schema field is
    short enough to offer — a lower-case street standing alone — and they get
    the FRAGMENT question only: `residual_of` would pay morphology for every
    word of the field to answer about names the capitalised windows already
    cover (measured: twice the work of the whole signal).

    `address_parts` and `cued_numbers` carry WHAT THE TEXT SAID THE STRING IS,
    not what it looks like, and that is the whole of Б28ter. A bare «26» means
    three different things and the text says which: under a schema key the
    schema calls `flat` it is a flat, after the word «кв.» it is a flat, after
    «дом» a house, after «контрольное число» the tail of a СНИЛС — and with
    nothing in front of it, it is somebody's quantity and is asked nothing.
    Each pair therefore travels with the role, or with the (type, side) its cue
    named, and the vault is asked exactly as narrowly as the restoring leg
    asked. Asked without the narrowing, a `flat` field found a substitute whose
    HOUSE carried that number and reported a value the restore had not even
    tried to replace.
    """

    named: set[str]
    words: set[str]
    address_parts: set[tuple[str, str]]
    cued_numbers: set[tuple[str, str | None, str | None]]

    def standing_in(self, restored: str) -> "_Candidates":
        """The same four groups, keeping only what survived restoration."""
        return _Candidates(
            {value for value in self.named if _still_standing(value, restored)},
            {value for value in self.words if _still_standing(value, restored)},
            {pair for pair in self.address_parts if _still_standing(pair[0], restored)},
            {item for item in self.cued_numbers if _still_standing(item[0], restored)},
        )

    def any(self) -> bool:
        return any(bool(group) for group in self)


def _written_candidates(text: str, for_tool: bool) -> _Candidates:
    """Every string the restoring leg offered the vault about this text, with
    the question it was offered to — see `_Candidates`."""
    general = {match.group() for match in token_re().finditer(text)}
    # THE v6 FINANCE FAMILY'S OWN SCAN, AND IT IS NOT REDUNDANT. `token_re` is
    # non-overlapping and leftmost-first, and the family's records are FREE-FORM
    # numbers: on «полис ДМС 437BX87160487» the PLATE pattern matches «С 437BX871»
    # — the last letter of the cue word and the head of the token — and the scan
    # resumes AFTER it, so the whole substitute is never a candidate here and a
    # leftover is reported as nothing. The restoring leg asks the same question
    # separately (`_restore_tokens_spans`) for the same reason; this is that
    # question on the reporting leg, so silence about a fake cannot survive.
    general |= {match.group()
                for match in ru_pii_v6.FINANCE_TOKEN_RE.finditer(text)}
    # …AND THE SAME QUESTION FOR THE UTILITY/ACCOUNT FAMILY, whose records are the
    # LAST patterns in `vault._token_re` because they are cue/key-typed rather than
    # format-anchored: a thirteen-digit air-ticket token is claimed by the ОГРН
    # pattern first and a Latin handle by nothing, so the reporting leg must ask
    # the family's own alternation too or a leftover fake would be reported as
    # silence. The restoring leg asks it separately for the same reason.
    general |= {match.group()
                for match in ru_pii_v6.UTILITY_TOKEN_RE.finditer(text)}
    if ASSETS.is_loaded:
        general |= {text[start:end] for start, end, words in spoken.numeral_runs(text)
                    if len(spoken.run_to_digits(words)) >= 10}
    # A PHONE TOKEN IS WRITTEN THE CUSTOMER'S WAY (vault `_digits_in_customer_
    # form`), so `TOKEN_RE`'s «+79…» shape no longer names it; every digit run
    # is offered and the vault answers by signature.
    general |= {match.group().strip() for match in _NUM_RUN.finditer(text)}
    # A NAME the model REWROTE no longer matches any token, so `TOKEN_RE` alone
    # would miss exactly the case this exists for. Capitalised runs are offered
    # too, and the vault decides which of them are made of its own words.
    general |= {surface for _start, _end, surface in _name_windows(text)}
    cued, addressed = _cued_candidates(text)
    if not for_tool:
        return _Candidates(general, set(), addressed, cued)
    words = {surface for _start, _end, surface in _tool_windows(text)}
    # AND THE LEAVES, BECAUSE THE RESTORING LEG WORKS ON LEAVES. `unmask_
    # arguments` parses the object and restores each string leaf on its own, so
    # a leaf that is nothing but a number — «92», «7359» — is asked there as a
    # whole (`_WHOLE_NUMBER` in `_restore_reformatted_spans`), while in the
    # serialised object it is far too short for `_NUM_RUN` and no window ever
    # proposed it. That is why the house number and the phone's digit tail
    # refused in silence.
    for key, leaf in _string_leaves(text):
        value = leaf.strip()
        if not value:
            continue
        if _WHOLE_NUMBER.fullmatch(value) or _DATE_SHAPE.match(value):
            general.add(value)
        role = _role_of_field(key)
        if role:
            addressed.add((value, role))
    return _Candidates(general, words, addressed, cued)


def _cued_candidates(text: str) -> tuple[set[tuple[str, str | None, str | None]],
                                         set[tuple[str, str]]]:
    """The numbers a CUE introduced, split the way `_restore_cued_numbers_spans`
    splits them: an address part goes to the address question with its role, and
    everything else to the digit question with the type and the side its cue
    named.

    THE CUE IS WHY A BARE NUMBER CAN BE ASKED ABOUT AT ALL. «последние четыре
    цифры 6359», «серия 4509», «дом 47», «кв. 83» — the restoring leg goes down
    to two digits here and nowhere else, because the cue says what the digits
    are and where they sit. Without a cue the same «47» is a quantity, and the
    reporting direction must be exactly as brave and no braver: the house cue
    was dropped from this set entirely, so a house refused in PROSE went out in
    silence while the same refusal in an argument was reported.
    """
    cued: set[tuple[str, str | None, str | None]] = set()
    addressed: set[tuple[str, str]] = set()
    for match in _CUE_NUMBER.finditer(text):
        if not _licensed_number_cue(text, match):
            continue
        number = match.group("num").strip()
        if not number:
            continue
        cue = match.group("cue").lower()
        if cue.startswith(_HOUSE_CUES):
            role = _CUE_ROLES.get(cue[:2], "house")
            addressed.add((number, role))
        else:
            kind, position = _cue_kind(cue)
            cued.add((number, kind, position))
    return cued, addressed


# Какую роль адреса называет подсказка перед числом — те же слова, что у
# `_HOUSE_CUES`, прочитанные по назначению и названные так же, как их называет
# `morph_places.split_roles`: «дом»→house, «корпус»→building, «кв»→flat,
# «подъезд»→entrance. `_restore_cued_numbers_spans` выводит роль из СОДЕРЖИМОГО
# подмены (в какой её части стоят эти цифры); здесь спрашивается то же самое,
# только ролью, которую назвал сам текст.
_CUE_ROLES = {"до": "house", "д.": "house", "ко": "building",
              "кв": "flat", "по": "entrance"}


def _string_leaves(raw: str) -> list[tuple[str, str]]:
    """(key, value) for every string leaf of a tool call's arguments — the same
    walk `unmask_arguments` restores by. Arguments that are not valid JSON are
    one nameless leaf, exactly as they are there."""
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return [("", raw)]
    out: list[tuple[str, str]] = []

    def walk(node: object, key: str) -> None:
        if isinstance(node, str):
            out.append((key, node))
        elif isinstance(node, list):
            for item in node:
                walk(item, key)
        elif isinstance(node, dict):
            for name, value in node.items():
                walk(value, str(name))

    walk(parsed, "")
    return out


def _still_standing(candidate: str, restored: str) -> bool:
    """This exact string is still in the restored text, on word boundaries.

    A substitute that resolved was replaced, so it is gone; one that was refused
    is untouched, so it is there. The boundaries matter for numbers above all:
    «92» inside «1992» is a different number, and reporting it would be the same
    cry-wolf this whole ordering exists to stop.

    `find` first, and the boundary test only where it hits, because the ordinary
    answer is that everything resolved and nothing is here to check.
    """
    if not candidate:
        return False
    at = restored.find(candidate)
    while at >= 0:
        before = restored[at - 1] if at else ""
        after = restored[at + len(candidate):at + len(candidate) + 1]
        if not _joins_a_word(before) and not _joins_a_word(after):
            return True
        at = restored.find(candidate, at + 1)
    return False


def _joins_a_word(character: str) -> bool:
    return bool(character) and (character.isalnum() or character == "_")


def _pieces_of_ours(asked: _Candidates, whole: set[str], vault: Vault) -> set[str]:
    """Those leftovers that are a PIECE of one of our substitutes — the refusals
    the restoring leg made in silence, named.

    THE QUESTION IS EXISTENCE, NOT IDENTITY, AND THAT IS THE POINT. Every
    fragment lookup on the restoring leg («whose substitute is this piece?»)
    answers only when the answer is unique and in reach; it had already said no
    about each of these, so asking it again would report nothing. What is asked
    here is the other half — «is this piece OURS at all?» — and combined with
    «it is still standing» it says exactly what the caller needs to know: a fake
    is in your tool call.

    ONE QUESTION PER STRING, AND IT IS THE ONE THE TEXT LICENSED. A word is a
    street name; a string under an address-role key or after an address cue is
    asked of that role and no other; a date-shaped value reads to the canonical
    the vault indexed a spoken substitute under; a number a cue introduced is
    asked of that cue's type at that cue's side. Nothing is asked about a string
    the text said nothing about — that was the shape-guessing Б28ter replaced,
    and it is where the false alarms this pass closed came from. What the text
    DOES name and the vault still cannot decide — a bare house number several
    substitutes wear, with no conversation to break the tie — is reported, and
    `surviving_substitutes` says why.
    """
    pieces: set[str] = set()
    for value, role in asked.address_parts:
        if value not in whole and _place_fragment_is_ours(value, role, vault):
            pieces.add(value)
    for value, kind, position in asked.cued_numbers:
        digits = "".join(character for character in value if character.isdigit())
        if value not in whole and len(digits) >= 2 and vault.digit_fragment_is_ours(
                digits, kind, position):
            pieces.add(value)
    for candidate in (asked.named | asked.words) - whole - pieces:
        if _DATE_SHAPE.match(candidate):
            if _date_is_ours(candidate, vault):
                pieces.add(candidate)
            continue
        digits = "".join(character for character in candidate if character.isdigit())
        if not digits:
            # A WORD IS A STREET NAME, and the street is the one address part a
            # substitute carries as words. Asked with no role it would also
            # answer about a house number written in words, which no schema does.
            if _place_fragment_is_ours(candidate, "street", vault):
                pieces.add(candidate)
        elif _still_a_whole_value(candidate) and vault.digit_fragment_is_ours(digits):
            # ЦЕЛОЕ ЗНАЧЕНИЕ, ПЕРЕПИСАННОЕ АГЕНТОМ, — не «кусок по форме». Это
            # ровно тот кандидат, который `_restore_reformatted_spans` отдаёт
            # `digit_fragment_owner` без сужения, потому что телефон, СНИЛС и
            # карта приходят целиком и отличаются от количества длиной, а не
            # догадкой: «92» сюда не попадает, потому что `_NUM_RUN` его не
            # предлагает и целым полем его предлагает только схема.
            pieces.add(candidate)
    return pieces


def _still_a_whole_value(candidate: str) -> bool:
    """A candidate `_restore_reformatted_spans` would have handed the digit
    signatures: a run long enough to be an identifier rather than a count. The
    floor is that function's own — three digits, a СНИЛС group — and it is read
    off the same constant so the two cannot drift apart."""
    digits = "".join(character for character in candidate if character.isdigit())
    return len(digits) >= _FRAGMENT_DIGIT_FLOOR


def _place_fragment_is_ours(candidate: str, role: str, vault: Vault) -> bool:
    """`Vault.place_fragment_is_ours` behind the guard every other morphology
    call on this leg carries: a diagnostic must never be the thing that turns a
    restored answer into a 500."""
    try:
        return vault.place_fragment_is_ours(candidate, role)
    except Exception:  # noqa: BLE001 - morphology must never break a response
        return False


def _date_is_ours(candidate: str, vault: Vault) -> bool:
    """A date-shaped leftover the vault holds under one of its readings. The
    SAME readings the restoring leg offered (`_date_readings` plus the canonical
    of a month written in words), because a reading it never asked about is a
    refusal that never happened."""
    value = candidate.strip()
    readings = [value, *_date_readings(value)]
    if not _DATE_ANY.match(value):
        canonical = _date_canonical(value)
        if len(canonical) == 10:
            readings.append(canonical)
    return any(vault.date_reading_is_ours(reading)
               for reading in readings if _DATE_ANY.match(reading))


class StreamDetokenizer:
    """Stateful wrapper over `unmask_stream_chunk` for the in-process proxy leg,
    where one object can own the carry for the life of a single stream."""

    def __init__(self, vault: Vault) -> None:
        self._vault = vault
        self._carry = ""

    def feed(self, chunk: str) -> str:
        emit, self._carry = unmask_stream_chunk(chunk, self._carry, self._vault, False)
        return emit

    def flush(self) -> str:
        emit, self._carry = unmask_stream_chunk("", self._carry, self._vault, True)
        return emit
