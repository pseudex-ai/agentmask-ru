"""The swap layer: tokenize text on the way to the model, detokenize on the way back.

Detection is decoupled — the caller passes the spans (from any detector), so the
proxy can use the full ensemble (regex + checksum + NER) and tests can use a
lighter one. Reverse uses longest-token-first to avoid prefix collisions.
"""

import json
import re

from pseudex.detect import Span
from pseudex import morph_names, morph_places
from pseudex.profiling import stage
from pseudex.vault import LOC_TOKEN_PATTERN, TOKEN_RE, Vault, name_key, place_key

# A number-like run (digits + phone separators), >=7 digits — a candidate for
# digit-core detokenization when the model reformatted a numeric token.
_NUM_RUN = re.compile(r"(?<![\d])[+(]?\d[\d\s().\-]{5,}\d(?!\d)")
# Значение поля целиком: только цифры и разделители, не меньше трёх цифр.
_WHOLE_NUMBER = re.compile(r"[+(]?\d[\d\s().\-]*\d(?:\D*)?")


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


def mask_text(text: str, vault: Vault, spans: list[Span]) -> str:
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
    return _splice(text, [
        (span.start, span.end, _token_for_text(span, vault))
        for span in spans
        if not vault.is_minted_token(span.value)
    ])


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
    token = vault.tokenize(span.value, span.entity_type)
    if span.entity_type == "LOC":
        # Same reason as NAME: a nominative phrase dropped into an oblique slot
        # reads as broken Russian, and broken Russian is what makes a model
        # rewrite the token instead of using it.
        case = morph_places.detect_case(span.value)
        if case is None or case == "nomn":
            return token
        return morph_places.inflect_place(token, case)
    if span.entity_type != "NAME":
        return token
    case = morph_names.detect_case(span.value)
    if case is None or case == "nomn":
        return token
    # Gender comes from the REAL person, not from re-reading the token. The two
    # agree by construction — the token was minted for this gender — and asking
    # the token again can only lose: a fake first name the dictionary happens
    # not to know (София) makes the whole span read as the wrong gender, and
    # then the surname is inflected as a man's.
    return morph_names.inflect_person(
        token, case, morph_names.detect_gender(span.value))


def unmask_text(text: str, vault: Vault, inflect: bool = True,
                for_tool: bool = False) -> str:
    """Replace tokens with their real values, then catch numeric tokens the model
    REFORMATTED via a digit-signature match.

    Candidates are found by SHAPE (`Vault.TOKEN_RE`) and resolved in batched
    indexed lookups, so the cost tracks the length of the answer rather than the
    size of the vault. The previous approach loaded every token the org had ever
    minted and substring-scanned the text once per token, which made an org with
    100k tokens pay 100k scans on every single response."""
    with stage("unmask.total"):
        restored = _restore_reformatted(
            _restore_tokens(text, vault, for_tool), vault, for_tool)
        return _restore_inflected(restored, vault, inflect, for_tool)


# The ГОСТ plate alphabet was chosen precisely because every letter in it has a
# Latin twin — that is why a Russian plate is readable abroad. It is also why a
# model happily rewrites «Р984ОМ003» as «R984OM003»: to it the two are the same
# string in two scripts. The rewritten form is no longer the token, so the vault
# misses it and the customer's tool receives the fake.
#
# Seen in a persona run, once in four round trips, on a real tool call. Phones
# have had a second line of defence since the digit-signature reindex — a plate
# is the same failure with a different alphabet, and this is its equivalent.
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
_DATE_ANY = re.compile(r"^(\d{1,4})[.\-/](\d{1,2})[.\-/](\d{2,4})$")


def _date_readings(value: str) -> list[str]:
    match = _DATE_ANY.match(value.strip())
    if not match:
        return []
    first, middle, last = match.groups()
    if len(first) == 4:
        return [f"{int(last):02d}.{int(middle):02d}.{first}"]
    if len(last) == 4:
        return [f"{int(first):02d}.{int(middle):02d}.{last}",
                f"{int(middle):02d}.{int(first):02d}.{last}"]
    return []


def _restore_tokens(text: str, vault: Vault, for_tool: bool = False) -> str:
    matches = list(TOKEN_RE.finditer(text))
    if not matches:
        return text
    candidates = {match.group() for match in matches}
    # Every way the model might have rewritten a token, offered alongside the
    # token itself. A miss costs one indexed point query; a hit is the difference
    # between the customer's tool receiving a real value and receiving a fake.
    readings: dict[str, list[str]] = {}
    for value in candidates:
        alternates = [value.translate(_PLATE_FOLD), value.translate(_PLATE_SOUND)]
        alternates.extend(_date_readings(value))
        readings[value] = [alt for alt in alternates if alt != value]

    asked = candidates | {alt for group in readings.values() for alt in group}
    values = vault.detokenize_many(asked, for_tool)

    def resolved(written: str) -> str | None:
        if written in values:
            return values[written]
        for alternate in readings.get(written, ()):
            if alternate in values:
                return values[alternate]
        return None

    spans: list[tuple[int, int, str]] = []
    for match in matches:
        value = resolved(match.group())
        if value is not None:
            if for_tool:
                value = _digits_in_form_of(match.group(), value)
            spans.append((match.start(), match.end(), value))
    return _splice(text, spans)


def _restore_reformatted(text: str, vault: Vault,
                         for_tool: bool = False) -> str:
    """Numeric tokens the model rewrote (+7… -> 8…, separators stripped) no longer
    match their minted shape, so they are resolved by digit signature instead."""
    runs = [(match, re.sub(r"\D", "", match.group())) for match in _NUM_RUN.finditer(text)]
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
        return text
    candidates: set[str] = set()
    for _, digits in runs:
        candidates.add(digits)
        if len(digits) >= 10:
            candidates.add(digits[-10:])
    resolved = vault.resolve_digit_signatures(candidates, for_tool)
    # БЕЗ РАННЕГО ВОЗВРАТА. Пустая выборка по сигнатурам — это ровно тот случай,
    # ради которого заведён разбор куска ниже: агент положил в поле часть
    # подмены, и целой сигнатуры у неё нет по построению.
    spans: list[tuple[int, int, str]] = []
    for match, digits in runs:
        # Full signature wins over the phone last-10 fallback.
        value = resolved.get(digits) or (resolved.get(digits[-10:]) if len(digits) >= 10 else None)
        if value is not None:
            if for_tool:
                value = _digits_in_form_of(match.group(), value)
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
        if not for_tool or len(digits) < 3:
            continue
        owner = vault.digit_fragment_owner(digits)
        if owner is not None:
            spans.append((match.start(), match.end(),
                          _same_shape(match.group(), owner[0])))
    return _splice(text, spans)


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
    real_digits = re.sub(r"\D", "", real)
    written_digits = re.sub(r"\D", "", written)
    if len(written_digits) < 3 or not real_digits:
        return real
    date_written = _DATE_ANY.match(written.strip())
    date_real = _DATE_ANY.match(real.strip())
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
_NAME_WORD = re.compile(r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?")

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
    for stop in list(ends):
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
    head = _CITY_HEAD.search(text[:start])
    if head is not None and head.end() == start:
        for stop in ends:
            candidates.add((head.start(), stop))
    return sorted(candidates, key=lambda pair: pair[1] - pair[0], reverse=True)


_FLAT_TAIL = re.compile(r",?\s*(?:кв|квартир\w*|офис\w*|оф)\.?\s*\d{1,4}")
# Подъезд, как его пишет МОДЕЛЬ: «подъезд 2», «под. 2», «подъезда 2».
_ENTRANCE_TAIL = re.compile(r",?\s*(?:под[ъь]езд\w*|под)\.?\s*\d{1,4}")
# Корпус/строение — такой же хвост, и стоит перед подъездом.
_BUILDING_TAIL = re.compile(r",?\s*(?:корп\w*|кор|стр|строен\w*|литер\w*)\.?\s*\d{1,4}")
# A house number as a MODEL writes it: bare, or behind «д.» / «дом» / «влад.».
# Bounded to four digits and never spanning a sentence, so it cannot swallow an
# order number that happens to follow the address.
_HOUSE_TAIL = re.compile(r",?\s*(?:(?:д|дом|вл|влад|владение)\.?\s*)?\d{1,4}"
                         r"(?:/\d{1,3})?[а-яё]?(?![\w])")
_CITY_HEAD = re.compile(r"(?-i:[А-ЯЁ])[а-яё-]+,\s*$")
# Город в начале самой ПОДМЕНЫ — чтобы понять, назвала его модель или нет.
_STREET_TYPE_WORD = re.compile(
    r"(?i)^(?:ул\.?|улиц\w*|пр-т|пр\.?|просп\w*|пер\.?|переул\w*|б-р|бульвар\w*|ш\.?|шоссе|пл\.?|площад\w*|"
    r"наб\.?|набережн\w*|проезд\w*|тупик\w*|алле\w*|дорог\w*|тракт\w*|линия|линии)$")
_CITY_OF_TOKEN = re.compile(r"^([А-ЯЁ][а-яё-]+),\s")


def _name_windows(text: str) -> list[tuple[int, int, str]]:
    """Every contiguous 1-3 word window of capitalised Cyrillic words.

    Windows rather than maximal runs, because a sentence-initial word is
    capitalised too: `Позвоните Ивану Щукину` is one run of three, and looking
    it up whole finds nothing while `Ивану Щукину` would have matched. Misses
    are free — an indexed point query that returns no row — so enumerating is
    cheaper than being clever about which word starts a sentence.
    """
    words = [(m.start(), m.end(), m.group()) for m in _NAME_WORD.finditer(text)]
    windows: list[tuple[int, int, str]] = []
    for i in range(len(words)):
        for size in (3, 2, 1):
            if i + size > len(words):
                continue
            start, end = words[i][0], words[i + size - 1][1]
            # Only if the words are adjacent — a window may not jump a comma or
            # a lowercase word, which would join two unrelated names.
            if re.fullmatch(r"[А-ЯЁа-яё\s-]+", text[start:end]) is None:
                continue
            windows.append((start, end, text[start:end]))
    return windows


def _restore_inflected(text: str, vault: Vault, inflect: bool = True,
                       for_tool: bool = False) -> str:
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

    for match in _PLACE_RUN.finditer(text):
        for start, end in _place_windows(text, match.start(), match.end()):
            surface = text[start:end]
            try:
                keys[(start, end)] = [place_key(surface)]
            except Exception:  # noqa: BLE001
                continue
            windows.append((start, end, surface))
    if not windows:
        return text
    resolved = vault.resolve_name_keys_typed(
        {k for group in keys.values() for k in group}, for_tool)
    # NO EARLY RETURN ON AN EMPTY KEY LOOKUP. The fragment fallback below is the
    # only thing that resolves «Филипп Алексеевич», and a fragment never has a
    # key hit by construction — returning here meant the fallback could only ever
    # run for text that had already resolved by some other window.
    spans: list[tuple[int, int, str]] = []
    taken: list[tuple[int, int]] = []
    for start, end, surface in sorted(windows, key=lambda w: w[1] - w[0], reverse=True):
        found = next((resolved[k] for k in keys.get((start, end), [])
                      if k in resolved), None)
        if found is None:
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
            owner = (_residual_owner(surface, vault, for_tool)
                     or _place_fragment(surface, vault, for_tool))
            if owner is None:
                continue
            found = owner
        entity_type, value = found
        if any(a < end and start < b for a, b in taken):
            continue
        taken.append((start, end))
        spans.append((start, end,
                      _in_case_of(value, surface, entity_type, inflect)))
    return _splice(text, spans)


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
    token = vault.place_owner(surface)
    if token is None:
        return None
    value, entity_type = vault.reveal(token, for_tool)
    if not value or entity_type != "LOC":
        return None
    if for_tool:
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
    if not (1 <= len(words) <= 2):
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
        # The role is read off EACH WORD ALONE, not off the phrase: the minted
        # token and the real value can be read in different orders as phrases
        # («Родион Тарасов» / «ерохин пётр»), and a phrase shape then maps a
        # surname onto a given name. A lone word has one reading.
        def role_of(word: str) -> str:
            shape = morph_names.name_shape(word)
            return shape[0] if len(shape) == 1 else ""
        picked = []
        for fake, real in zip(fake_parts, real_parts):
            if fake.casefold() in wanted or morph_names.to_nominative(fake).casefold() in wanted:
                role = role_of(fake)
                same_role = [candidate for candidate in real_parts if role and role_of(candidate) == role]
                picked.append(same_role[0] if len(same_role) == 1 else real)
        if len(picked) == len(surface.split()):
            return entity_type, " ".join(picked)
    return entity_type, value


def _in_case_of(value: str, surface: str, entity_type: str = "NAME",
                inflect: bool = True) -> str:
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
        return value
    if entity_type in ("LOC", "ADDR"):
        case = morph_places.detect_case(surface)
        if case is None or case == "nomn":
            return value
        return morph_places.inflect_place(value, case)
    case = morph_names.detect_case(surface)
    if case is None or case == "nomn":
        return value
    return morph_names.inflect_person(value, case, morph_names.detect_gender(value))


# Longest token across our format-preserving tokens is well under this.
_STREAM_KEEP = 64


# A run of capitalised words, or of digits and the separators that hold a number
# together. These are the shapes `_restore_inflected` slides its windows over, so
# a stream must never cut inside one.
_STREAM_RUN_RE = re.compile(
    r"[А-ЯЁA-Z][а-яёa-z]+(?:[\s,]+[А-ЯЁA-Z][а-яёa-z]+)*"
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


def unmask_arguments(raw: str, vault: Vault) -> str:
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

    Arguments that are not valid JSON fall back to flat text: a model is free
    to emit a broken object, and refusing to detokenise it would send a FAKE to
    the tool — the one outcome worse than imperfect text.
    """
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return unmask_text(raw, vault, inflect=False, for_tool=True)

    def walk(node: object) -> object:
        if isinstance(node, str):
            # VERBATIM, NOT AGREED. A tool executes on the value; grammar is a
            # property of prose. See `_in_case_of`.
            return unmask_text(node, vault, inflect=False, for_tool=True)
        if isinstance(node, list):
            return [walk(item) for item in node]
        if isinstance(node, dict):
            # Keys are the tool's own schema, not customer text — but a token
            # can only ever appear in a value, so rewriting keys would be a way
            # to break the schema and never a way to restore a value.
            return {key: walk(value) for key, value in node.items()}
        return node

    return json.dumps(_join_addresses_deep(walk(parsed), parsed, vault),
                      ensure_ascii=False)


def _join_addresses_deep(restored: object, original: object, vault: Vault) -> object:
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
        joined = _join_address_fields(restored, original, vault)
        if not isinstance(joined, dict):
            return joined
        return {key: _join_addresses_deep(value, original.get(key), vault)
                for key, value in joined.items()}
    if isinstance(restored, list) and isinstance(original, list):
        return [_join_addresses_deep(value, original[index] if index < len(original) else None, vault)
                for index, value in enumerate(restored)]
    return restored


# Имена полей, которыми схемы инструментов называют части адреса. Роль читается
# из имени, а не из формы значения: имя — это единственное, что видит и модель,
# когда решает, что куда положить.
_FIELD_ROLES: tuple[tuple[str, str], ...] = (
    ("street", "street"), ("house", "house"), ("building", "house"),
    ("flat", "flat"), ("apartment", "flat"), ("apt", "flat"), ("sflat", "flat"),
    ("entrance", "entrance"), ("porch", "entrance"), ("floor", "floor"),
    # The settlement is a field of its own in every delivery schema (CDEK
    # `city`, Yandex `locality`); without a role here a bare fake city in it
    # was never asked about and reached the tool as «Сортавала».
    ("city", "city"), ("locality", "city"), ("town", "city"), ("settlement", "city"),
)


def _role_of_field(name: str) -> str:
    parts = name.lower().split("_")
    for word, role in _FIELD_ROLES:
        if word in parts:
            return role
    return ""


def _join_address_fields(restored: object, original: object, vault: Vault) -> object:
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
    groups: dict[str, dict[str, str]] = {}
    for key, value in addressed.items():
        role = _role_of_field(key)
        prefix = key.lower().rsplit(role, 1)[0].strip("_")
        groups.setdefault(prefix, {})[key] = value
    out = dict(restored)
    for group in groups.values():
        out = _join_one_address(out, {key: value for key, value in group.items() if key in fragments},
                                group, vault)
    return out


def _join_one_address(restored: dict[str, object], fragments: dict[str, str],
                      evidence: dict[str, str], vault: Vault) -> dict[str, object]:
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
    owners = {vault.place_owner(value) for value in evidence.values()}
    owners.discard(None)
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
        if len(head) == 2 and not _STREET_TYPE_WORD.match(head[0]) and not _STREET_TYPE_WORD.match(head[1]):
            from pseudex import address as address_mod
            from pseudex.assets import ASSETS
            register = ASSETS.get().address if ASSETS.is_loaded else None
            if (register is not None and address_mod._gar_reaches(head[1], register)
                    and not address_mod._gar_reaches(head[0], register)):
                roles["city"] = head[0].strip(" ,.")
                roles["street"] = head[1]
    out = dict(restored)
    for key in fragments:
        role = _role_of_field(key)
        part = roles.get(role)
        if part:
            # THE FORM IS THE AGENT'S: digits where it wrote digits, no type
            # word where it wrote none. See `morph_places.part_in_form_of`.
            out[key] = morph_places.part_in_form_of(fragments[key], part, role)
    return out


def residual_tokens(text: str, vault: Vault) -> list[str]:
    """Minted tokens still standing in text that has already been detokenized.

    THE SIGNAL EVERY PERSONA ASKED FOR, in the same words three times: «мне
    хватило бы заголовка X-Pseudex-Residual». When the model reorders a name,
    shortens it, or reformats a plate, the restored form no longer matches and
    the FAKE goes to the customer's tool — with a 200, empty counters and nothing
    in the log. Their code cannot find out, so they cannot fail closed on their
    own side.

    Read-only and cheap: the candidates are the same shapes `unmask_text` already
    scans for, and each is one indexed lookup that MISSES for a real value and
    HITS for a substitute we minted. A hit here means one thing only — this
    string is ours, and it should not have survived.
    """
    candidates = {match.group() for match in TOKEN_RE.finditer(text)}
    # A NAME the model REWROTE no longer matches any token, so `TOKEN_RE` alone
    # would miss exactly the case this exists for. Capitalised runs are offered
    # too, and the vault decides which of them are made of its own words.
    candidates |= {surface for _start, _end, surface in _name_windows(text)}
    if not candidates:
        return []
    known = vault.detokenize_many(candidates)
    residual = {value for value in candidates if value in known}
    residual |= {value for value in candidates
                 if value not in known and vault.residual_of(value) is not None}
    # MAXIMAL WINDOWS ONLY. «Римма Цветкова» is one leftover, not three; a caller
    # reading a count would otherwise see the same defect three times and could
    # not tell one damaged name from several.
    return sorted(value for value in residual
                  if not any(value != other and value in other
                             for other in residual))


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
