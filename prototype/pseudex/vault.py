"""Token vault — persistent (SQLite, stays in RF) + canonical, per customer.

Two production-critical properties this adds over the in-memory version:
  - PERSISTENCE: the value<->token map survives restarts / multiple instances,
    so tokens stored in conversation history stay reversible (fixes the
    "model uses old token -> order not found" failure).
  - CANONICALIZATION: the same real value in different formats
    (+7 999.. / 8 999.. / 89991234567) maps to ONE token, so the model sees a
    consistent identity across turns and sessions.

Tokens are format-preserving and checksum-invalid (see _render_token), so the
model copies them verbatim and they never coincide with a real person's ID.
"""

import copy
import functools
import re
import secrets
import string

from pseudex import credentials
from pseudex.assets import ASSETS
from pseudex.normalize import normalize
import threading
import time

from pseudex.fuzzy import within_one_typo
from pseudex import date_form, morph_names, morph_places, notation, spoken, translit
from pseudex.notation import looks_dictated
from pseudex.spoken import (email_from_words, numeral_runs,
                            plate_from_words, run_to_digits)
from pseudex.profiling import stage
from pseudex.ru_pii import validate_inn, validate_luhn, validate_ogrn, validate_snils
from pseudex import schema
from pseudex.sqlite_setup import (
    Connection,
    VAULT_STORE,
    VaultLocked,
    connect as sqlite_connect,
    connect_readonly,
    # NOT `sqlite3.IntegrityError`: the SQLCipher driver's exception classes are
    # not subclasses of the stdlib ones, so a handler naming the stdlib class
    # never fires. See `sqlite_setup`'s docstring — the INSERT-race handler below
    # is the one that matters.
    Error as SqliteError,
    IntegrityError,
)

_PLACE_CASES = ("nomn", "gent", "datv", "accs", "ablt", "loct")


def _rand_digits(count: int) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(count))


def count_values_since(db_path: str, since: float) -> int:
    """Distinct real values first protected since `since`, across every org in
    this installation.

    THE BILLING METER. One row is one real person's datum, once, forever — so a
    returning customer costs nothing and a value re-sent a thousand times costs
    what it cost the first time.

    Deliberately NOT the audit event count, which is what this used to be.
    Audit rows are written on a mask-cache MISS, so the same phone in four
    different messages counted three times; the count moved with
    PSEUDEX_MASK_CACHE_SIZE, which the customer sets, and with the worker count,
    because each worker holds its own cache. A meter the customer can lower with
    an env var, and which charges more for running a bigger container, is not a
    meter.

    Opened read-only and closed immediately: this runs on the licence renewal
    thread a few times a day, and holding a fourth connection to the vault for
    that would be a connection to keep correct forever.
    """
    try:
        conn = connect_readonly(db_path, VAULT_STORE)
    except (OSError, SqliteError, VaultLocked):
        return 0
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM tokens WHERE first_seen >= ?", (since,)
        ).fetchone()
        return int(row[0]) if row else 0
    except SqliteError:
        # No vault yet, or the column predates the migration. Zero is the honest
        # answer and it under-bills, which is the safe direction.
        return 0
    finally:
        conn.close()


_INTERNAL_CAPITAL_RE = re.compile(r"([а-яё])([А-ЯЁ])")



# HOW LONG A CONVERSATION'S LINKS ARE WORTH KEEPING, and why they must expire.
#
# `tokens` grows with the customer's distinct values and that is the product;
# `place_parts` grows with CONVERSATIONS, which is unbounded in a container that
# runs for months. The rows are also the only place a conversation identity is
# persisted, so keeping them for ever would quietly turn a scope meant to bound
# a decision into a permanent record of who talked when.
#
# A day is generous for what they are for: resolving «Ленина 14» against an
# address named earlier in the SAME dialogue. A dialogue that spans more than a
# day has had the full address re-sent in its transcript anyway.
_PLACE_PART_TTL = 24 * 60 * 60
# Swept at most once an hour per process. A DELETE on every insert would put a
# scan on the request path for a table that grows slowly; a timer would be a
# thread to supervise. This is neither.
_PLACE_SWEEP_INTERVAL = 60 * 60
_last_place_sweep = 0.0


def _digits_of(value: str) -> str:
    """The digits of a value, whether it was written or SPOKEN.

    A phone said out loud carries no digit at all, so the plain strip returns
    nothing — and «+7 916…» and «восемь девятьсот шестнадцать…» are the same
    number said two ways. Collapsing them is the same rule that already
    collapses «+7 999…», «8 999…» and «89991234567»: one identity, one
    substitute, so the model sees a stable person across turns and the tool
    receives the number the customer actually gave.
    """
    digits = re.sub(r"\D", "", value)
    if digits:
        return digits
    runs = numeral_runs(value)
    if len(runs) == 1 and len(runs[0][2]) >= 4:
        return run_to_digits(runs[0][2])
    return ""


# A SPACE IS A SEPARATOR TOO: «дата рождения 14 03 1987» is how the voice
# register writes a date, and unread it drew a random year for the substitute
# (the agent's `age` off by decades) and spliced «1403-19-87» into the ISO
# field on the way back (fresh-seed v4, derive-000/004).
_NUMERIC_DATE_RE = re.compile(r"(\d{1,4})[./ -](\d{1,2})[./ -](\d{1,4})")
_MONTH_WORD_DATE_RE = re.compile(r"(?i)(\d{1,2})\s+([а-яё]+)(?:\s+(\d{4}))?")


def _date_canonical(value: str) -> str:
    """«dd.mm.yyyy» from any way a date of birth is written or said."""
    text = re.sub(r"(?i)\s*(?:г\.?|года|год)\s*$", "", value.strip())
    numeric = _NUMERIC_DATE_RE.search(text)
    if numeric:
        first, middle, last = numeric.groups()
        if len(first) == 4:
            year, month, day = first, middle, last
        else:
            day, month, year = first, middle, last
        if len(year) == 2:
            year = ("20" if int(year) <= time.localtime().tm_year % 100 else "19") + year
        return f"{int(day):02d}.{int(month):02d}.{year}" if len(year) == 4 else ""
    worded = _MONTH_WORD_DATE_RE.fullmatch(text)
    if worded:
        month = spoken._month_value(worded.group(2).lower().replace("ё", "е"))
        if month is not None:
            return (f"{int(worded.group(1)):02d}.{month:02d}.{worded.group(3)}" if worded.group(3)
                    else f"{int(worded.group(1)):02d}.{month:02d}")
    return spoken.date_from_words(text)


def canonicalize_person(value: str, cases: tuple[str, ...]) -> str:
    """`canonicalize("NAME", …)` with the cases the sentence allows the name to
    stand in. With a governor the joint reading decides even a lone word: «у
    Иванова» is a man, whatever a lone «Иванова» would be."""
    if not cases:
        return canonicalize("NAME", value)
    surface = _INTERNAL_CAPITAL_RE.sub(r"\1 \2", value.strip())
    return morph_names.to_nominative_governed(surface, cases)


def canonicalize(entity_type: str, value: str) -> str:
    """Normalize a value so equivalent forms collapse to one key.

"""
    if entity_type == "PHONE":
        digits = _digits_of(value)
        if len(digits) == 11 and digits[0] in "78":
            digits = "7" + digits[1:]
        elif len(digits) == 10:
            digits = "7" + digits
        return "+" + digits if digits else value
    if entity_type in ("SNILS", "INN", "CARD", "PASSPORT"):
        # AN EMPTY CANONICAL IS A COLLISION GENERATOR, and it became reachable
        # the moment the engine learned to hear an identifier DICTATED ALOUD.
        # «четыре два ноль девять…» has no digits, `re.sub` returned the empty
        # string, and every spoken СНИЛС in the tenant collapsed onto ONE row —
        # two different people sharing one substitute, which is the single
        # failure this product treats as unacceptable. Measured, not imagined:
        # two distinct spoken СНИЛС came back as the same token.
        return _digits_of(value) or value
    if entity_type == "DOB":
        # ONE DATE OF BIRTH IS ONE KEY, however it was said: «21.09.1980»,
        # «21 сентября 1980» and «двадцать первое сентября восьмидесятого
        # года» were three rows, and the spoken one restored to the tool as
        # the words the customer said — the agent's schema asks for a date,
        # the control writes 21.09.1980, and the axis counted every spoken date
        # as lost (v3 DOB 48% -> 32% the day the engine learned to hear them).
        # The digits form is what a CRM stores and what the substitute mirrors.
        canonical = _date_canonical(value)
        if canonical:
            return canonical
        return value.strip().lower()
    if entity_type == "EMAIL":
        # ПРОДИКТОВАННАЯ ПОЧТА — РУССКАЯ ФРАЗА, А НЕ АДРЕС. `lower()` над
        # «ситникова собака мэйл точка ру» возвращает ту же фразу, и она уезжала
        # в поле `email`, где вызов инструмента не срабатывал НИКОГДА. Разбор
        # живёт рядом с распознаванием той же формы и честно называется
        # реконструкцией: логин человека — то, что он сам когда-то выбрал.
        spoken = email_from_words(value)
        if spoken:
            return spoken
        return value.strip().lower()
    if entity_type == "NAME":
        # THE KEY IS THE PERSON, NOT THE WORDING. Without this, `Иванов Пётр`,
        # `Иванову Петру` and `Иванова Петра` are three rows, so one client
        # becomes three people: the agent's memory fills with strangers, the
        # cross-dialogue stability the landing promises does not hold, and the
        # protected-value counter multiplies by however many cases the customer
        # happened to write. Exactly parallel to what the PHONE branch above
        # already does by collapsing +7/8/no-separators to one signature.
        #
        # A LONE SURNAME MAY NOT BE COLLAPSED ACROSS GENDERS. «Иванова» is the
        # feminine nominative of Иванова and the masculine genitive of Иванов;
        # pymorphy3 ranks the masculine reading higher, so a woman named by
        # surname alone was keyed as «Иванов» — and that is the name
        # `detokenize` handed the customer's tool. Worse, she then shared a row
        # with any real Иванов on file: two people, one token, which is the one
        # failure this product treats as unacceptable.
        #
        # This is a different function from the one that indexes TOKENS.
        # `name_key` also calls `to_nominative`, but on the fake name, so
        # resolving a token the model inflected is untouched — that distinction
        # is the whole reason the guard belongs here and not in `to_nominative`,
        # where it broke every substitute's round trip instead.
        # A MISSED SPACE IS STILL ONE PERSON. Detection finds «ГончароваАнна»,
        # but the key kept it glued and it became a second row — so the model met
        # two people out of one typing slip.
        surface = _INTERNAL_CAPITAL_RE.sub(r"\1 \2", value.strip())
        if morph_names.lone_nominative_gender(surface) is not None:
            return surface
        # WRITTEN ORDER IS PRESERVED HERE, deliberately. Sorting the parts into
        # slots makes one person one key whichever way round they were written —
        # and it also decides what `detokenize` hands the tool, so «Клиент Елена
        # Попова» came back «Клиент Попова Елена». The customer's own word order
        # is part of the value; the key must not eat it.
        #
        # Order-invariance belongs in the LOOKUP instead, where it costs nothing:
        # see `_same_person_reordered`.
        return morph_names.to_nominative(surface)
    if entity_type == "PLATE":
        # A PLATE IS THE SAME CAR IN EITHER CASE, and the ГОСТ alphabet was
        # chosen so every letter has a Latin twin — «а123вс777», «А123ВС777» and
        # «A123BC777» are one number to everyone except a string comparison.
        # Keyed as written, one car became three.
        # ПРОДИКТОВАННЫЙ НОМЕР — ЭТО РУССКАЯ ФРАЗА, А НЕ НОМЕР. `upper()` над
        # «а двести шестьдесят три о ка регион шестьдесят шесть» возвращает ту
        # же фразу заглавными, и она уезжала в аргумент инструмента вместо
        # «А263ОК66». Разбор живёт в `spoken.py`, рядом с распознаванием той же
        # формы; пустая строка означает «фраза номером не является», и тогда
        # прежний путь остаётся в силе.
        spoken = plate_from_words(value)
        if spoken:
            return spoken
        # SPACES AND HYPHENS ARE PRESENTATION, NOT IDENTITY. «А123ВС777» and
        # «А 123 ВС 777» are one car, but the separator survived into the key
        # (CARD/SNILS/INN collapse it through `_digits_of`; PLATE was not in
        # `_NUMERIC_TYPES`), so the spaced form the detector emits and the tight
        # form the customer typed minted two tokens. Stripped HERE, in the key,
        # and only in the key: `detokenize` still returns the ORIGINAL, so the
        # tool receives the grouping the customer actually wrote.
        return re.sub(r"[\s-]+", "", value.strip().upper()
                      .translate(str.maketrans("ABEKMHOPCTYX", "АВЕКМНОРСТУХ")))
    if entity_type == "LOC":
        # THE ADDRESS HAD NO KEY AT ALL — the raw surface was used, so one place
        # written nine ways was nine rows and the model met nine addresses.
        # Normalised hard on purpose: `detokenize` returns the ORIGINAL for
        # every type except NAME, so the customer's tool still receives the
        # string they wrote and only the row it finds changes.
        return morph_places.address_key(value)
    return value.strip()


def _fake_snils() -> str:
    """A СНИЛС that PASSES the ПФР check.

    It was minted invalid on purpose — «a substitute must never be somebody's
    real number» — and an agent told to verify identifiers refused it and
    never called the tool: 12 of 24 `validate` triples on the 04.09 live run,
    the whole class that remained. The fear behind the invalid sum is answered
    elsewhere now, the way it is for every other type: a fake NAME is a real
    name and a fake street a real street, and what keeps a real bearer from
    being read as our token is the CONVERSATION SCOPE (`tokens.minted_in`),
    not the number's impossibility; the other direction — a substitute equal
    to a value this customer already holds — is refused by `_unique_token`
    against the vault. A random valid СНИЛС is somebody's in about one case
    in seven across Russia, and in the one dialogue it was minted for the
    chance that that person walks in is nil. Numbers at or below 001-001-998
    are the earliest real registrations, exempt from the check, and are not
    drawn (research/2026-09-03-checksum-valid-substitutes.md, revised).
    """
    for _ in range(50):
        body = _rand_digits(9)
        if int(body) <= 1001998:
            continue
        total = sum(int(digit) * (9 - index) for index, digit in enumerate(body))
        control = total if total < 100 else (0 if total in (100, 101) else total % 101)
        if control in (100, 101):
            control = 0
        candidate = f"{body[:3]}-{body[3:6]}-{body[6:9]} {control:02d}"
        if validate_snils(candidate):
            return candidate
    raise RuntimeError("could not generate a checksum-valid СНИЛС")


# VALID TO EVERY ALGORITHM, IMPOSSIBLE FOR A PERSON. A model told to check
# identifiers refused a checksum-invalid substitute and never called the tool
# (v4 small: 16 of 36 `validate` triples), and the product's reason for the
# invalid sum — a substitute must never be somebody's real number — is just as
# real. Both are kept where the number's STRUCTURE allows it: an ИНН carries
# the tax region in its first two digits and «00» is no region; a passport
# series carries the ОКАТО region and «00» is no region; a card's first digit
# is the industry, and «0» is reserved for ISO/TC 68, no bank issues under it.
# A СНИЛС has no such field, so its substitute is valid and NOT impossible —
# guarded by the conversation scope instead, like a name (see `_fake_snils`).
# Sources and arithmetic in research/2026-09-03-checksum-valid-substitutes.md.
_INN_WEIGHTS_10 = (2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN_WEIGHTS_11 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8)
_INN_WEIGHTS_12 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8)


def _inn_check_digit(digits: str, weights: tuple[int, ...]) -> str:
    total = sum(int(d) * w for d, w in zip(digits, weights))
    return str(total % 11 % 10)


def _fake_inn(original: str = "") -> str:
    """Region «00», valid check digits, the parsed IDENTITY's length (10 or 12).

    THE SURFACE IS NOT THE IDENTITY. `original` is what the customer wrote —
    and for a number DICTATED ALOUD that text carries no digit at all, so
    counting its characters minted a ten-digit ИНН for a twelve-digit one. The
    substitute then had the wrong number of digits and the spoken form could not
    be rendered at all (the renderer aligns the fake to the mention's own
    grouping and refuses when the digit counts disagree), so the model read a
    ten-digit fake where the customer had said twelve digits. `_digits_of` is
    the same reading `canonicalize` keys the row by, so nothing about the stored
    key changes — only the length of what is minted stops depending on how the
    number happened to be written.
    """
    twelve = len(_digits_of(original)) == 12
    for _ in range(50):
        if twelve:
            body = "00" + _rand_digits(8)
            body += _inn_check_digit(body, _INN_WEIGHTS_11)
            body += _inn_check_digit(body, _INN_WEIGHTS_12)
        else:
            body = "00" + _rand_digits(7)
            body += _inn_check_digit(body, _INN_WEIGHTS_10)
        if validate_inn(body):
            return body
    raise RuntimeError("could not generate a checksum-valid ИНН in region 00")


def _luhn_check_digit(body: str) -> str:
    total = 0
    for index, ch in enumerate(reversed(body)):
        digit = int(ch)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


# THE LENGTHS A CARD ARRIVES IN, and the identity is what decides. `validate_luhn`
# accepts any run of thirteen or more, the spoken classifier reads 13..19 as a
# card, and the digit path types only the sixteen-digit one — so a card read
# aloud in eighteen or nineteen digits was answered with a sixteen-digit
# substitute: a different shape, and one the customer's own validator refuses.
# Sixteen stays the default for a caller with no mention at all (the shape
# invariant test), so nothing already minted changes its string.
_CARD_DEFAULT_LENGTH = 16
_CARD_LENGTHS = range(13, 20)


def _card_length(original: str) -> int:
    """The card identity's length — never the surface's digit count, which is
    zero for anything dictated aloud."""
    digits = _digits_of(original)
    return len(digits) if len(digits) in _CARD_LENGTHS else _CARD_DEFAULT_LENGTH


def _fake_card(length: int = _CARD_DEFAULT_LENGTH) -> str:
    """MII «0», Luhn-valid, exactly `length` digits — no issuer exists under that
    first digit, whatever the length. Grouped in fours with the remainder last
    («0123 4567 8901 2347», «0123 4567 8901 2345 02»): the sixteen-digit string
    is character for character what this generator has always returned, so every
    stored row keeps resolving, and the 18/19 grouping is the one the shape
    recognizer below accepts."""
    for _ in range(50):
        body = "0" + _rand_digits(length - 2)
        body += _luhn_check_digit(body)
        if validate_luhn(body):
            return " ".join(body[at:at + 4] for at in range(0, len(body), 4))
    # Returning `body` here used to emit an UNFORMATTED 16-digit string, which
    # TOKEN_RE does not match — an unreversible token, silently.
    raise RuntimeError("could not generate a Luhn-valid card number under MII 0")


# Enough that a collision streak is impossible in practice, small enough that
# a genuinely exhausted pool fails fast instead of stalling the caller.
_TOKEN_MINT_ATTEMPTS = 200

# Every type whose token is DIGITS and which a model may therefore reformat.
# The six document types were added when they were introduced and this tuple was
# not: their rows got NULL signatures, so a driver's licence echoed back as
# `9912345678` instead of `99 12 345678` resolved to nothing and the tool ran on
# the FAKE number — which this file elsewhere calls worse than a miss.
_NUMERIC_TYPES = (
    "PHONE", "CARD", "SNILS", "INN", "PASSPORT",
    "OMS", "ACCOUNT", "DRIVER_LICENSE", "VEHICLE_DOC", "INTL_PASSPORT", "OGRN",
)


# ЧТО ВОЗВРАЩАЕТСЯ ВМЕСТО ПОДМЕНЫ, И ПОЧЕМУ ЭТО ДВА РАЗНЫХ ОТВЕТА.
#
# Имя возвращается КАНОНИЧЕСКИМ — «Иванов Пётр», а не «Иванову Петру»: падеж
# нужен предложению, а не CRM. Всё остальное возвращается КАК НАПИСАНО, потому
# что телефон «+7 999 123-45-67» клиент так и записал, и нормализовать его за
# него мы не вправе.
#
# ПРОДИКТОВАННОЕ ВСЛУХ ЛОМАЕТ ЭТО ПРАВИЛО. «восемь девятьсот двадцать шесть
# четыреста сорок…» — это тоже «как написано», и именно оно уезжало в аргумент
# инструмента: модель получила подмену ЦИФРАМИ, честно передала цифры, а мы на
# обратном пути положили в поле `phone` предложение по-русски. Ни одна CRM
# такого не примет. 20+ случаев живого прогона: телефон, СНИЛС, паспорт, карта.
#
# Признак различает их без нового столбца и без флага на спане: у
# продиктованного значения в `original` НЕТ НИ ОДНОЙ ЦИФРЫ, а в `canonical` они
# есть — `_digits_of` собирает их из числительных. У записанного цифрами обе
# формы цифровые, и правило его не касается: «+7 999 123-45-67» приходит в
# инструмент ровно так, как его написали.
#
# Разделение ровно то же, что уже сделано для падежа: АРГУМЕНТ ДОСЛОВЕН, ПРОЗА
# СОГЛАСОВАНА. В прозе агент продолжает говорить клиенту его же словами.
_VALUE_SQL = ("CASE WHEN entity_type='NAME' THEN canonical ELSE original END")
# Обе формы разом, чтобы выбор делал Python. В SQL он был условием про цифры и
# промахнулся мимо почты: канон «sitnikova@mail.ru» цифр не содержит, и правило
# «в каноне есть цифры, а в написанном нет» её не узнавало. Условие вынесено
# туда, где его видно и можно проверить тестом.
_VALUE_SQL_BOTH = "entity_type, canonical, original"

# ЭТОТ ДИАЛОГ ЧЕКАНИЛ СТРОКУ — ИЛИ НИКАКОЙ. Условие четырёх пофрагментных
# поисков (`place_owner`, `place_owner_by_street`, `date_owner`,
# `digit_fragment_owner`): фрагмент подмены не уникален — «Полевая 35»,
# «35», «15.05.2025» выглядят одинаково у всех, — поэтому владельца ищут
# только среди строк СВОЕГО разговора.
#
# ПУСТАЯ ОБЛАСТЬ — ЭТО НЕ «ЛЮБАЯ», НО И НЕ «НИ ОДНА». Раньше при пустой области
# условие ВЫБРАСЫВАЛОСЬ целиком, и каждый из четырёх поисков отвечал по всему
# заказчику. На плече маскирования области всегда есть (её выводит
# `conversation_key`), а вот `/unmask`, `/unmask_chunk` и `/unmask_arguments`
# выводить её не из чего — и сужение выключалось ровно там, где значение
# ОТДАЮТ: диалог B получал в поле `street` настоящий адрес диалога A, чужой дом,
# чужую дату и последние четыре цифры настоящего телефона и СНИЛС (Б28).
#
# ЗАКРЫТЬ ЭТО ОТКАЗОМ НЕЛЬЗЯ: документированный клиент сайдкара
# (`docs/integration-diva-backend-api.md`, `POST /unmask {org_id, response}`)
# `conversation_id` не шлёт вовсе, и «нет разговора — нет ответа» молча ломает
# работающую интеграцию на четырёх классах фрагментов сразу. Поэтому плечо без
# названного разговора спрашивает ВЕСЬ ВОЛТ и отвечает ТОЛЬКО при единственном
# кандидате (`_fragment_scopes`); двусмысленность — отказ с видимым остатком.
# Это тот же принцип единственного кандидата, на котором стоит сама область
# разговора (CLAUDE.md, «The conversation scope»): у заказчика с одним диалогом
# про эту улицу отвечать по-прежнему есть чем, а два диалога с одной улицей
# больше не путаются. Целая подмена уникальна и резолвится всегда — её мог
# назвать только тот, кому мы её отдали, и она идёт мимо этих поисков.
#
# Две записи одного условия, потому что один запрос идёт по `tokens` напрямую,
# а три — через JOIN с алиасом `k`. Собирать вторую из первой заменой строки
# значило бы прятать имя таблицы в вызове.
_MINTED_HERE_JOINED = " AND (k.minted_in=? OR k.minted_in IS NULL OR k.minted_in='')"
_MINTED_HERE = " AND (minted_in=? OR minted_in IS NULL OR minted_in='')"
# Сколько владельцев одной основы улицы стоит читать, чтобы ответить «один или
# несколько» (`_place_key_owners`). Больше полусотни — это уже «несколько» при
# любом продолжении списка, и вызывающий поворачивает в безопасную сторону:
# единственного кандидата нет, остаток виден.
_PLACE_OWNER_CAP = 50
# Сколько владельцев ещё имеет смысл спрашивать «а это не одно ли место»
# (`_one_identity`). Цепочку `extends` строит только короткое упоминание и
# выросший из него полный адрес — это две строки, изредка три; десяток владельцев
# одной основы — это десяток мест при любом прочтении. Потолок не косметический:
# у запроса `_one_identity` нет индекса по `extends`, поэтому он перебирает все
# строки заказчика, и задавать его на каждый кандидат ответа нельзя.
_ONE_IDENTITY_CAP = 4
# Сколько строк стоит прочитать, чтобы ответить «этот кусок цифр вообще наш?»
# (`digit_fragment_is_ours`). Отвечает первая подходящая, а подходят почти все
# найденные: единственный отбор — совпадение длин настоящего и подменного
# значения. Предел бережёт попадание; промах читает всё и стоит ровно того же,
# что уже стоило восстановление (`digit_fragment_owner` по тому же куску).
_DIGIT_FRAGMENT_PROBE = 16
# Сколько цифр подряд делают написанную агентом строку кандидатом в ЦЕЛУЮ
# подмену (`whole_substitute_signatures`). Шесть — короче самого короткого
# числового значения, которое мы чеканим целиком (дата — восемь цифр, телефон
# — одиннадцать), и длиннее любого куска, ради которого этот вопрос задаётся.
# Спрашивать волт о двузначном количестве значило бы объявлять подмену «уже
# написанной» из-за случайного совпадения двух цифр.
_WHOLE_SIGNATURE_MIN = 6

# Типы, у которых канонизация даёт САМО ЗНАЧЕНИЕ в нормальной форме, а не ключ
# для поиска. Для них и только для них аргументу отдаётся канон.
# DOB is here for the same reason as a phone: a birth date said aloud is a
# phrase the tool cannot store, and the agent's schema asks for a date.
_CANONICAL_IS_THE_VALUE = frozenset(_NUMERIC_TYPES) | {"EMAIL", "PLATE", "DOB"}

# `looks_dictated` переехал в `notation` вместе с остальными вопросами о нотации
# (импорт выше): «это фраза или значение» — вопрос о НОТАЦИИ, и вторая его
# читалка разошлась бы с первой ровно так, как расходятся все вторые читалки.


def _pick_value(entity_type: str, canonical: str, original: str,
                for_tool: bool) -> str:
    """Что вернуть вместо подмены: имя — каноническим, остальное — как написано.

    Исключение одно и оно про инструмент: продиктованную вслух фразу инструмент
    исполнить не может, поэтому в аргумент уходит канон. В прозе агент
    продолжает говорить клиенту его же словами.
    """
    if entity_type == "NAME":
        return canonical
    # ТОЛЬКО ТАМ, ГДЕ КАНОН — ЭТО ЗНАЧЕНИЕ. У адреса `canonical` не значение, а
    # ПОИСКОВЫЙ КЛЮЧ (`address_key`), и отдать его инструменту — то же, что
    # отдать хеш. Первая версия правила смотрела только на «фразу из русских
    # слов», а продиктованный адрес — тоже фраза из русских слов: LOC в
    # аргументе рухнул с 84.5% до 30.6% на всём корпусе, и поймал это прогон, а
    # не рассуждение.
    # A DATE GOES BACK AS THE CUSTOMER WROTE IT, on both legs. Its substitute
    # mirrors the customer's notation (digits, month in words, or spoken), so
    # an agent that copies gets the customer's own words and an agent that
    # rewrites («1997-08-04») gets the real date re-rendered in ITS notation
    # by the restorer. The dictated exception stays for identifiers, whose
    # substitutes are still minted in digits.
    if (for_tool and entity_type in _CANONICAL_IS_THE_VALUE and entity_type not in ("DOB", "DATE")
            and looks_dictated(original or "", canonical or "")):
        return canonical
    # NO REPAIR — THE CUSTOMER'S LITERAL STRING, TYPO AND ALL. Fixing a
    # mistyped street to the register spelling («золоторожксий» →
    # «золоторожский») was us CHANGING the parameter the agent passes, which
    # is exactly what the product promises never to do: «содержимое из волта,
    # форма — агента». If the agent wrote the address correctly, we mirror
    # that; if it copied the customer's typo, the tool gets the typo — the
    # same string it would have got without us. Correcting the customer's
    # address is the AGENT's business, not the gateway's. (Measured cost of the
    # old repair: 26 addresses scored as changed on the public benchmark, every
    # one a repair the ground truth — the customer's own words — did not ask
    # for.) `repair_street` stays available as an opt-in host policy, off by
    # default.
    return original


def name_key(token: str) -> str:
    """Case-invariant signature of a personal name: its nominative, lowercased.

    `Руслану Хвостову`, `Руслана Хвостова` and `Руслан Хвостов` all reduce to
    one key, so a token the model inflected still resolves to the real value.
    """
    return morph_names.to_nominative(token).lower()


# ТРИ ПОДПИСИ, И ТРЕТЬЯ — ЭТО ЦЕНА, КОТОРУЮ ПЛАТИТ ХОСТ. Заказчик объявляет
# «Ленина 14», а клиент спрашивает «а вы на ул. Ленина, д. 14?»: `address_key`
# держит родовое слово, поэтому два написания ОДНОГО адреса ключуются по-разному
# и объявление работало бы только для той формы, которую хост угадал.
# `street_house_key` для того и написан — это ключ, который два написания одного
# места ВСЕГДА разделяют.
#
# ОН НАМЕРЕННО СТАЛКИВАЕТСЯ ПО ГОРОДАМ, и здесь это стоит денег: клиент, живущий
# на «Ленина 14» в другом городе, уйдёт к модели открытым. Квартира, подъезд или
# корпус в его упоминании дают другой ключ и защищают его; голое «Ленина 14»
# защищено не будет. Хост объявляет СВОИ значения и платит за объявление сам —
# ровно как с `pseudonym_scope`.
def _own_street_key(text: str) -> str:
    """`street_house_key`, но ТОЛЬКО для упоминания без частей мельче дома.

    КВАРТИРА — ЭТО ТО, ЧТО ОТЛИЧАЕТ ДОМОХОЗЯЙСТВО ОТ ЗДАНИЯ, и без этой оговорки
    объявленный адрес компании накрывает жильца того же дома: «везите на ленина
    14 квартира 7» ушло бы к модели ОТКРЫТЫМ, потому что `street_house_key`
    намеренно обрывается на квартире. Адрес компании такой частью не бывает, а
    адрес клиента — сплошь и рядом, так что цена объявления остаётся на том, кто
    его сделал, и не перекладывается на его клиентов.
    """
    shape = morph_places.place_shape(text)
    if shape.get("has_flat") or shape.get("has_entrance") or shape.get("has_building"):
        return ""
    return morph_places.street_house_key(text)


_OWN_SIGNATURES = (name_key, lambda text: morph_places.address_key(text),
                   _own_street_key)


def fold_key(canonical: str) -> str:
    """Case- and ё-insensitive signature of a name, for the LOOKUP only.

    A person is not a capitalisation and not a diaeresis. Keyed by the written
    form, «Гончарова Анна» and «гончарова анна» were two rows, so the model met
    two people; «Пётр» and «Петр» were two more, and ё->е is 53% of all real
    Russian misspelling — a norm, not a typo.

    A SEPARATE signature rather than a normalised key, because `canonical` is
    also what `detokenize` hands the customer's tool: folding it there would put
    «гончарова анна» into a CRM that was told «Гончарова Анна». First writer
    wins the display, everybody shares the row.
    """
    return canonical.casefold().replace("ё", "е")


def place_key(token: str) -> str:
    """Case-invariant signature of a LOC, stored in the same column as a name's.

    The column is called `name_key` for historical reasons — people came first —
    and holds whichever signature suits the row's type. One index, one purpose:
    find the row this token belongs to, whatever case it was written in.
    """
    # A SIGNATURE, not a normalised phrase. Morphological normalisation was
    # tried first and is too fragile for places: the phrase has variable
    # structure (generic word, name, house number, or a bare settlement), and
    # each shape needed its own rule. The signature keeps only what inflection
    # cannot change — the name's stem and the house number — the same trick that
    # has always made a reformatted phone resolvable.
    return morph_places.match_signature(token) if token else ""


def _place_numbers_collide(token: str, original: str) -> bool:
    numbers = re.findall(r"\d+", token)
    if any(a != b and a in b for a in numbers for b in numbers) or len(numbers) != len(set(numbers)):
        return True
    if not original:
        return False
    folded = " ".join(morph_places._fold_cardinals(morph_places.address_key(original).split()))
    return bool(set(numbers) & set(re.findall(r"\d+", folded)))


def _digits_in_customer_form(original: str, canonical_token: str) -> str:
    """The fake's digits laid into the original's separators and prefix.
    «89896866953» -> «89077509228», «8-999-106-11-83» -> «8-964-510-18-44»,
    «+7 (912) 257-90-12» -> «+7 (935) 179-44-08»; a form the splice cannot
    line up with (a dictated phone, a different digit count) keeps the
    canonical «+7…»."""
    fake = re.sub(r"\D", "", canonical_token)
    real = re.sub(r"\D", "", original)
    # Ten or eleven digits is a phone; anything longer carries an extension
    # («+79162148803, доб. 214») or a second number, and laying the fake's
    # tail across those positions would spread the phone into the extension.
    if len(real) not in (10, 11) or not fake:
        return canonical_token
    # Keep the customer's prefix convention: whatever stands before the last
    # ten digits is theirs («8», «+7», «7», nothing), the last ten are ours.
    out: list[str] = []
    tail = fake[-10:]
    taken = 0
    kept_prefix = len(real) - 10
    for ch in original:
        if ch.isdigit():
            if taken < kept_prefix:
                out.append(ch)
            else:
                out.append(tail[taken - kept_prefix])
            taken += 1
        else:
            out.append(ch)
    rendered = "".join(out)
    return rendered if re.sub(r"\D", "", rendered)[-10:] == tail else canonical_token


def _digits_laid_like(original: str, token: str) -> str:
    """The fake's digits under the customer's own separators — «4509 123456»
    → «0006 543820», «11223344595» → «81893751149», «4276-1600-1234-5675»
    → «0879-8274-8727-6119». The identifier's shape at the mint mirrored a
    REGISTER («dd dd dddddd», «ddd-ddd-ddd dd»), not the customer, so an
    agent copying the substitute copied our grouping and the tool received
    a form the customer never wrote. Only when the digit counts agree; a
    different count (a dictated number, an extension) keeps the canonical.
    The way back never depended on the grouping: numeric tokens are indexed
    by their digit signature."""
    fake = re.sub(r"\D", "", token)
    real = re.sub(r"\D", "", original)
    if not fake or len(fake) != len(real):
        return token
    digits = iter(fake)
    return "".join(next(digits) if ch.isdigit() else ch for ch in original)


def _digit_signatures(token: str, entity_type: str) -> tuple[str | None, str | None]:
    """Digit signature of a NUMERIC token, so a token the model reformatted
    (separators stripped, +7 rewritten as 8) still resolves. Phones also key on
    their last 10 digits because the country code varies. Non-numeric types get
    NULL so they stay out of the signature indexes.

    A PLATE IS NOT DIGITS, AND IT WAS NULL — which is why «е 079 он 583» (the
    agent spaced the substitute out) resolved to nothing and the fake drove into
    the customer's validator. Its content signature is letters AND digits with
    the alphabet folded (both Latin readings, see `notation.plate_signature`),
    so any rewriting — separators, case, alphabet, dictation — finds the row.
    The signature is asked of the token's CONTENT, not of its spelling: a plate
    the mint showed in words has no digits at all, and a signature read off the
    words themselves would be a string of letters nobody could ever match."""
    if entity_type == "PLATE":
        signature = notation.plate_signature(notation.plate_content(token))
        return (signature, None) if signature else (None, None)
    if entity_type not in _NUMERIC_TYPES:
        return None, None
    digits = re.sub(r"\D", "", token)
    if not digits:
        return None, None
    tail = digits[-10:] if entity_type == "PHONE" and len(digits) >= 10 else None
    return digits, tail


# The WHOLE date, not just its year. Comparing years alone puts «30.09.2026»
# in the past for all of 2026 — which is most of the traffic that matters, since
# a booking is usually made for later this year.
_DATE_PARTS = re.compile(r"(?:^|\D)(\d{1,4})[.\-/ ](\d{1,2})[.\-/ ](\d{1,4})(?:\D|$)")


def _is_future(original: str) -> bool:
    """Is this date after today?

    THE YEAR IS READ BY `_date_canonical`, NOT BY A SECOND RULE HERE. This
    function used to parse the date itself and turned a two-digit year into
    20YY unconditionally: «10.4.82» became 2082, the date read as future, and
    a date of BIRTH was replaced by a substitute in 2027 — breaking the rule
    that a fake date of birth keeps the year and the side of today. The
    canonical reader pivots on the current year («82» → 1982, «02» → 2002),
    and one phrase must have one reader; the repo has paid for a second one
    before (`street_house_key` and the city).

    Unreachable until dates with a two-digit year began to be detected at all,
    and then found by the public benchmark rather than by the battery, because
    no case in the battery carried one.
    """
    canonical = _date_canonical(original or "")
    if canonical and len(canonical) == 10:
        day, month, year = (int(part) for part in canonical.split("."))
    else:
        match = _DATE_PARTS.search(original or "")
        if not match:
            return False
        first, middle, last = (int(part) for part in match.groups())
        day, month, year = (last, middle, first) if first > 31 else (first, middle, last)
        if year < 100:
            year += 2000
    today = time.localtime()
    return (year, month, day) > (today.tm_year, today.tm_mon, today.tm_mday)


def _fake_date(original: str) -> str:
    """A date on the SAME side of today as the one it replaces.

    The generator drew its year from 1960-1999 unconditionally, so «доставка
    30.09.2026» became «02.12.1973» — and a model reading a delivery booked for
    1973 does the reasonable thing: it treats the year as a typo and rewrites
    it. The rewritten string is no longer the token, nothing resolves, and the
    FAKE reaches the customer's tool. Two personas found this independently on
    live traffic, one booking a patient into 1977 and one moving a delivery to
    1973, both silently and both with a 200.

    A date of birth is always in the past and an appointment always in the
    future. Preserving that is what stops the model from correcting the token in
    the first place — the fix belongs in the generator, not in the lookup, and
    the lookup was widened separately for the reformatting it cannot prevent.
    """
    year_now = time.localtime().tm_year
    # READ BEFORE THE BRANCH. It stood inside the past-date branch only, and the
    # same-side-of-today block below read it for a FUTURE date too — a courier
    # interval or a clinic slot in a tool RESULT — and raised UnboundLocalError
    # on the result leg of the r2 run (06.09): the SDK turned it into a tool
    # error, the model saw «техническая ошибка», retried or gave up, and 304
    # gateway-arm replies said so while every record read `done`.
    known = _date_canonical(original)
    if _is_future(original):
        # Future: near enough to read as a real booking, never today itself, so
        # the substitute cannot be mistaken for «сегодня» by a model reasoning
        # about relative dates.
        year = year_now + secrets.randbelow(3) + 1
    else:
        # A PAST DATE KEEPS ITS YEAR. The agent derives the AGE from a date of
        # birth — a clinic's `patient.age`, an insurer's tariff — and from a
        # random year the derivation is wrong by construction (live v4: every
        # `age` field in the `derive` family). The year alone identifies
        # nobody (≈1.5 million people a year in Russia); the day and the month,
        # which do, stay fake — the same line the settlement of an address
        # draws (`_settlement_of`).
        year = int(known[-4:]) if len(known) == 10 else 1960 + secrets.randbelow(max(1, year_now - 1960))
    # …AND THE SAME SIDE OF TODAY. The year alone left the AGE off by one:
    # real 11.09, fake 17.08, today 05.09 — the real birthday is still to come
    # this year and the fake one has passed, so `patient.age` read 70 in the
    # control and 71 through the gateway (37 triples on the 05.09 medium run,
    # every `age` divergence there was). The day and the month stay fake; only
    # which side of today they fall on is kept, which is one bit.
    today = time.localtime()
    real_month_day = ((int(known[3:5]), int(known[:2])) if len(known) >= 5 and known[2] == "." else None)
    month, day = secrets.randbelow(12) + 1, secrets.randbelow(28) + 1
    if real_month_day is not None and not _is_future(original):
        today_month_day = (today.tm_mon, today.tm_mday)
        for _ in range(64):
            if (month, day) != today_month_day and ((month, day) < today_month_day) == (real_month_day < today_month_day):
                break
            month, day = secrets.randbelow(12) + 1, secrets.randbelow(28) + 1
    rendered = f"{day:02d}.{month:02d}.{year}"
    # A DATE THE CUSTOMER SAID IS REPLACED BY A DATE IN WORDS. «родился
    # одиннадцатого сентября пятьдесят пятого» was masked as «родился
    # 28.03.1972 пятьдесят пятого» — digits in a spoken sentence, with the real
    # year left standing beside them (9 of 9 spoken dates of birth on the 05.09
    # medium run). The substitute mirrors the customer's own register, century
    # and «года» included (`spoken.date_to_words`); it is indexed by its
    # canonical so the ISO the agent writes for it still resolves.
    if original and not _is_future(original) and not any(ch.isdigit() for ch in original):
        words = spoken.date_to_words(rendered if len(known) == 10 else rendered[:5], original)
        if words:
            return words
    # …AND A DATE WRITTEN IN DIGITS OR WITH THE MONTH IN WORDS IS REPLACED IN
    # THE SAME NOTATION: «2 июня 1975» by «19 июля 1975», «10.4.82» by
    # «15.9.82», an ISO date by an ISO date. The substitute changed the
    # notation before the agent saw it, an agent that copies verbatim copied
    # our «19.07.1975», and the tool received a form the customer never
    # wrote (25 of 27 dates of birth on the public benchmark). The way back
    # reads every one of these shapes (`token_re`, `_date_readings`) and
    # renders the real date like the agent's.
    return date_form.render_like(rendered, original) if original else rendered


def _fake_phone() -> str:
    """A mobile number whose 11 digits are deliberately NOT a valid СНИЛС.

    Both are 11-digit runs, so about 1% of random phone tokens pass the СНИЛС
    checksum — measured: 198 of 20 000. When that happened the token came back in
    a later turn, СНИЛС outranked PHONE in overlap resolution (6 against 5), and
    the re-masking guard missed it because detection reports the digits without
    the leading `+` while the minted token has it. The phone was then re-masked
    into a fake СНИЛС: the person's number changed mid-conversation and
    detokenization returned the wrong value to the tool.

    This is the same rule the СНИЛС, ИНН and card generators already follow — a
    token must never be a valid instance of ANY type, not just its own."""
    for _ in range(200):
        candidate = "+79" + _rand_digits(9)
        if not validate_snils(candidate[1:]):
            return candidate
    raise RuntimeError("could not generate a phone that is not a valid СНИЛС")


def _fake_ogrn(length: int) -> str:
    """ОГРН/ОГРНИП whose check digit is deliberately WRONG, so the token can
    never coincide with a real registered entity."""
    for _ in range(200):
        candidate = _rand_digits(length)
        if not validate_ogrn(candidate):
            return candidate
    raise RuntimeError("could not generate a checksum-INVALID ОГРН")


@functools.lru_cache(maxsize=4)
def _first_names_by_gender(version: str) -> dict[str, tuple[str, ...]]:
    """Split the leased first-name pool by gender, ONCE, using morphology.

    Derived rather than shipped as two lists: the pool is leased data and the
    split is an algorithm, so this keeps the bundle unchanged. Names morphology
    cannot classify fall back to the -а/-я ending, which is reliable for Russian
    GIVEN names (the masculine exceptions — Никита, Илья, Фома, Кузьма — are all
    in the dictionary and never reach the fallback). Keyed on the bundle version
    so a fresh lease with a different pool rebuilds it (and unload clears it).
    """
    buckets: dict[str, list[str]] = {"masc": [], "femn": []}
    for name in ASSETS.get().fakes.first:
        gender = morph_names.given_name_gender(name)
        buckets[gender or ("femn" if name.endswith(("а", "я")) else "masc")].append(name)
    return {"masc": tuple(buckets["masc"]), "femn": tuple(buckets["femn"])}


def _place_identity(canonical: str) -> tuple[str, ...]:
    """An address canonical without its street-type words, the spoken numbers
    folded to digits («сто» and «100» are one house, as in `street_house_key`)."""
    return tuple(morph_places._fold_cardinals(
        [part for part in canonical.split() if part not in morph_places._GENERIC]))


def _street_stem(short_key: str) -> str:
    """The street words of a `street_house_key` («заречный 57» → «заречный»)."""
    return " ".join(token for token in short_key.split() if not token[:1].isdigit())


def _street_stems_match(left: str, right: str) -> bool:
    """One street: equal, or one typo apart on a word of five letters or more —
    the same tolerance `_keys_match` gives the whole key."""
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) < 5 or len(right) < 5:
        return False
    return within_one_typo(left, right) or within_one_typo(_stem_of_word(left), _stem_of_word(right))


def _keys_match(left: str, right: str) -> bool:
    """Two `street_house_key`s name one place: equal, or the same numbers with
    street stems one typo apart. The customer's «дзержнского сорок четыре»
    and the register's «ул Дзержинского, д 44» keyed as two streets and got
    two substitutes — the typo is the customer's, the place is one."""
    if left == right:
        return True
    a, b = left.split(), right.split()
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x == y:
            continue
        if x.isdigit() or y.isdigit() or len(x) < 5 or len(y) < 5:
            return False
        # The register's word is LEMMATISED («пушкина» -> «пушкин») and the
        # customer's mistyped one is not (it is unknown to morphology, so its
        # spelling is kept), so «пушкна» stood two edits from the key of its
        # own street. Compared as STEMS — the inflectional ending off both
        # sides — they are one typo apart.
        if not (within_one_typo(x, y) or within_one_typo(_stem_of_word(x), _stem_of_word(y))):
            return False
    return True


_ENDING_RE = re.compile(r"(?:ого|ему|ому|ыми|ими|ая|яя|ый|ий|ой|ые|ие|ым|им|ом|ем|ах|ях|ов|ев|а|я|ы|и|е|у|ю|о)$")


def _stems_related(left: str, right: str) -> bool:
    """One stem is the other or begins with it (both at least four letters)."""
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 4 and longer.startswith(shorter)


def _stem_of_word(word: str) -> str:
    stem = _ENDING_RE.sub("", word)
    return stem if len(stem) >= 4 else word


def _same_house(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    """Two house identities name one house — exactly, or with the street one
    typo apart (`_keys_match`); the litera and every number must agree."""
    return _keys_match(" ".join(left), " ".join(right))


def _house_identity(canonical: str, has_city: bool) -> tuple[str, ...]:
    """The street and the house AS WRITTEN — litera included — of a canonical,
    without the city and without anything finer than the house.

    `street_house_key` is deliberately tolerant (it drops the litera, so a
    short mention may omit it) and is only ever used to FIND candidates; the
    decision to link is taken on this. The register answers three neighbours
    on one street — «д 10», «д 10А», the same house in the next town — and a
    tolerant decision joined them into one substitute."""
    parts = _place_identity(canonical)
    if has_city and parts:
        parts = parts[1:]
    out: list[str] = []
    for part in parts:
        if part in morph_places._SHORT_KEY_STOP:
            break
        out.append(part)
    return tuple(out)


def _street_stem(phrase: str) -> str:
    """The street's last word, folded and lemmatised, or "" when there is none."""
    street = morph_places.split_roles(phrase).get("street", "") if phrase else ""
    if not street:
        return ""
    words = [word for word in re.split(r"[\s,.]+", street.casefold().replace("ё", "е"))
             if word and word not in morph_places._GENERIC and not morph_places._GENERIC_STEMS.match(word)]
    if not words:
        return ""
    parses = morph_places.MORPH.parse(words[-1])
    return parses[0].normal_form if parses else words[-1]


def _stands_in_named_role(token_digits: str, digits: str, start: int,
                          position: str | None) -> bool:
    """Стоит ли кусок `digits`, найденный в цифрах подмены на месте `start`, в
    роли, которую подмена НЕСЛА, — то есть на краю, который эта роль называет.

    СЕРЕДИНА НЕ НОСИТ ИМЕНИ (Б29). `position` называет край, который назвала
    подсказка или поле схемы; `None` значит «спрашивающий края не назвал», а НЕ
    «где угодно внутри цифр». Внутри — это утверждение о НАШЕЙ строке, а не о
    том, чьё число написал агент: у заказчика с полусотней диалогов его
    собственное «количество: 218» лежит внутри цифр ровно одной фейковой трубки
    почти всегда, и на место количества МОЛЧА вставали три цифры ЧУЖОГО
    НАСТОЯЩЕГО телефона — порча данных в CRM и раскрытие через одну дверь. Край
    — единственное место куска, у которого есть имя: серия паспорта это начало,
    номер — конец, последние четыре цифры телефона или карты — конец,
    продиктованное тело СНИЛС — начало. Сузить вместо этого ОБЛАСТЬ поиска
    пробовали 23.09.2026: пропадала разложенная по полям целая подмена, и молча.

    ОДНА ФУНКЦИЯ НА ДВА ВОПРОСА, И ЭТО НЕ ЭКОНОМИЯ СТРОК. Восстановление
    (`_digit_fragments_in`) и сигнал (`digit_fragment_is_ours`) обязаны
    спрашивать ровно одно и то же: написанные порознь, они однажды разойдутся —
    и наружу это выйдет ложной тревогой на верном вызове либо молчащим отказом.
    """
    at_start = start == 0
    at_end = start + len(digits) == len(token_digits)
    if position == "start":
        return at_start
    if position == "end":
        return at_end
    return at_start or at_end


def _offsets(token_digits: str, digits: str) -> list[int]:
    """Все смещения, на которых этот кусок стоит в цифрах подмены. Один разбор
    на обе политики поиска (`_digit_fragments_in` и `_digit_fragments_tiled`),
    чтобы они не разошлись в том, ГДЕ кусок стоит; расходятся они только в том,
    какое из этих мест считают названным."""
    at: list[int] = []
    start = token_digits.find(digits)
    while start >= 0:
        at.append(start)
        start = token_digits.find(digits, start + 1)
    return at


def _placements(token_digits: str, digits: str, position: str | None) -> list[int]:
    """Смещения, на которых этот кусок стоит В НАЗВАННОЙ РОЛИ — то есть на краю.
    Отбор — `_stands_in_named_role`, см. там."""
    return [start for start in _offsets(token_digits, digits)
            if _stands_in_named_role(token_digits, digits, start, position)]


def _tiling(token_digits: str, runs: tuple[str, ...]) -> frozenset[tuple[int, str]]:
    """МЕСТА ПЛИТОК: разбиение цифр подмены числами ОДНОГО вызова — встык,
    целиком, минимум двумя плитками, без нахлёста и без остатка. Пустое
    множество, когда такого разбиения нет.

    МЕСТА, А НЕ «ДА/НЕТ», И ЭТО РЕШАЕТ ОТДЕЛЬНЫЙ ДЕФЕКТ (Б29). Ответ «эта
    подмена разбита вызовом» верен и про число, которое в разбиении НЕ
    участвует: «серия + номер + количество» разбивают паспорт серией и номером,
    а количество лишь оказалось рядом — и, спрошенное потом, оно получало
    настоящие цифры паспорта. Плитка отвечает только за себя: кусок наш, если
    он САМ является одной из плиток, покрывших подмену.

    ПОЧЕМУ РАЗБИЕНИЕ, А НЕ ВХОЖДЕНИЕ (Б29). «Эти цифры лежат внутри одной нашей
    подмены» — утверждение о НАШИХ строках, и у заказчика с полусотней диалогов
    оно истинно почти для любых трёх цифр: так его собственное количество молча
    уезжало в CRM цифрами чужого настоящего телефона. «Эти цифры вместе с
    соседними полями составляют подмену ЦЕЛИКОМ» — утверждение о ВЫЗОВЕ: так
    модель раскладывает одно значение по полям схемы (серия + номер паспорта —
    это все десять цифр), и случайно так не складывается. Точное покрытие
    выбрано вместо «двух непересекающихся мест» именно поэтому: покрытие — это
    строго более сильное утверждение о том, что написал агент.

    ПЛИТКА НЕСЁТ РОЛЬ БЕЗ КРАЯ, И ТОЛЬКО ОНА. Край — единственное место куска, у
    которого есть имя, когда о вызове ничего не известно (`_stands_in_named_role`);
    но схема, разложившая значение по всем своим полям, называет КАЖДОЕ из них,
    включая среднее — код оператора между страной и номером, внутренние группы
    СНИЛС и карты. Там роль называет не край, а само разбиение, и требовать
    вдобавок края значило бы терять середину молча.

    ПОЧЕМУ РАЗБИЕНИЕ, А НЕ ВХОЖДЕНИЕ (Б29). «Эти цифры лежат внутри одной нашей
    подмены» — утверждение о НАШИХ строках, и у заказчика с полусотней диалогов
    оно истинно почти для любых трёх цифр: так его собственное количество молча
    уезжало в CRM цифрами чужого настоящего телефона. «Эти цифры вместе с
    соседними полями составляют подмену ЦЕЛИКОМ» — утверждение о ВЫЗОВЕ: так
    модель раскладывает одно значение по полям схемы (серия + номер паспорта —
    это все десять цифр), и случайно так не складывается. Точное покрытие
    выбрано вместо «двух непересекающихся мест» именно поэтому: покрытие — это
    строго более сильное утверждение о том, что написал агент.

    ДВЕ ПЛИТКИ МИНИМУМ. Одной «разбивается» любая подмена, равная ей целиком, —
    а это уже не фрагмент, его находит целая сигнатура (`detokenize_many`).

    Лишние числа вызова остаются лишними, и остаются ими до конца: паспорт
    двумя полями разбивает паспортную подмену и тогда, когда рядом стоит
    количество, — но количество плиткой не становится и ответа не получает."""
    # Кусок короче двух цифр вопроса не задаёт (`digit_fragment_owner`), и
    # плиткой быть не может: одной цифрой мостится что угодно.
    unused = [run for run in runs if len(run) >= 2]
    laid: list[tuple[int, str]] = []

    def cover(at: int) -> bool:
        if at == len(token_digits):
            return len(laid) >= 2
        for index, run in enumerate(unused):
            if not run or not token_digits.startswith(run, at):
                continue
            unused[index] = ""
            laid.append((at, run))
            if cover(at + len(run)):
                unused[index] = run
                return True
            laid.pop()
            unused[index] = run
        return False

    return frozenset(laid) if cover(0) else frozenset()


def _wears_parts_in_role(token: str, stems: tuple[str, ...], numbers: tuple[str, ...],
                         role: str) -> bool:
    """Носит ли подмена эти части ИМЕННО В ЭТОЙ РОЛИ своего адреса.

    `token_parts` держит части без роли — на прямом пути роль и не нужна, кусок
    ищется как строка. Обратный, сообщающий вопрос без неё называет нашим не то:
    поле `flat` с числом 26 находило подмену, у которой 26 стоит в НОМЕРЕ ДОМА.
    Восстановление такую строку не трогает (оно роль проверяет), значит отказа
    не было и докладывать не о чем.

    Роль, которой у подмены нет вовсе, — это «нет», а не «может быть»: наши
    подмены квартир не несут, и ни одно число под ключом `flat` не наше.
    """
    part = morph_places.split_roles(token).get(role, "")
    if not part:
        return False
    if numbers and not stems:
        # ЧИСЛО СРАВНИВАЕТСЯ С ЧИСЛОМ, И МОРФОЛОГИЯ ЗДЕСЬ НИ ПРИ ЧЁМ. Это самый
        # частый вопрос этого слоя (номер дома под ключом схемы), а
        # `signature_parts` разбирает фразу через pymorphy — на владельце,
        # который и так уже стоил одного разбора адреса, второй не нужен.
        return set(numbers) <= set(re.findall(r"\d+", part))
    part_stems, part_numbers = morph_places.signature_parts(part)
    return set(stems) <= set(part_stems) and set(numbers) <= set(part_numbers)


_SETTLEMENT_MARKER_RE = morph_places.SETTLEMENT_MARKER_RE


def _capitalised(phrase: str) -> str:
    """«нижний новгород» -> «Нижний Новгород», «санкт-петербург» -> «Санкт-Петербург»."""
    return " ".join("-".join(part[:1].upper() + part[1:] for part in word.split("-"))
                    for word in phrase.split())


def _settlement_of(original: str) -> str:
    """The settlement the original names, in the nominative — KEPT REAL.

    THE CITY IS NOT PERSONAL DATA, AND HIDING IT BROKE THE AGENT. 152-ФЗ
    (ст. 3 п. 1) makes a person identifiable by a combination; a city alone
    identifies nobody, which is why the engine has always let a bare «это в
    самара» through in the clear. The same city INSIDE an address was replaced
    by a fake town, so the model held two cities for one place — its own
    «Самара, улица Мятная 151» composed from what it was shown, and «Чернь,
    улица Мятная 151» from the directory — and answered «адрес не найден»
    (live v4, `compare`: 29 of 42 triples). Every derivation the agent makes
    from the city (postcode, delivery zone, time zone) was wrong too, by
    construction. What identifies the household — the street and the house —
    stays fake; what the law does not protect stays true. A settlement that
    stands alone (no street) still draws a fake in `_fake_place`, because
    there the whole span IS the settlement.
    """
    city = morph_places.split_roles(original).get("city", "") if original else ""
    city = _SETTLEMENT_MARKER_RE.sub("", city.strip(" ,."))
    if not city or not re.fullmatch(r"[А-Яа-яЁё][А-Яа-яЁё -]*", city):
        return ""
    return _capitalised(morph_places.phrase_to_nominative(city).replace("ё", "ё"))


def _fake_city(original: str) -> str:
    """A city of the same GENDER as the one it replaces.

    Gender is not cosmetic here, it decides whether the case can be read back.
    Russian feminine place names collapse in the oblique cases — «Сортавале» is
    dative, prepositional and genitive at once — so a masculine city replaced by
    a feminine one leaves the restorer guessing, and «Санкт-Петербурге» came back
    «Санкт-Петербурга». The same rule that makes a fake NAME agree with the real
    person's gender applies to places, for the same reason.
    """
    cities = ASSETS.get().fakes.cities
    wanted = morph_places.place_gender(original) if original else None
    pool = [city for city in cities
            if morph_places.place_gender(city) == wanted] if wanted else []
    return secrets.choice(pool or cities)


@functools.lru_cache(maxsize=4)
def _usable_streets(version: str) -> tuple[str, ...]:
    """Fake streets whose every case reduces to the SAME key.

    «Ясеневый» does not: in the prepositional it is «Ясеневом», and pymorphy3
    reads that as ЯСЕНЕВО — a real Moscow district — so the key became
    «ясенево» while the minted token was keyed «ясеневый». The candidate was
    found in the model's reply and then failed the lookup, and the fake reached
    the tool. Measured at 4-7 addresses per 120 on an obliquely written street,
    silently.

    Names have had this check since «Яровым» could not be resolved back to
    «Яровой»; places had nothing equivalent, which is the same lesson unlearned
    on the other entity. DERIVED, not a hand-kept second list, so a street added
    to the pool cannot reintroduce the class unnoticed.
    """
    # BOTH GENDERS OF GENERIC, because the substitute mirrors the original's
    # shape and the adjective agrees with whichever word it lands beside. That
    # is where «Ясеневый» breaks and «Ясеневая» does not: only the masculine
    # prepositional «Ясеневом» collides with the district, so a check written
    # against «улица» alone declares the whole pool healthy.
    usable: list[str] = []
    for raw in ASSETS.get().fakes.streets:
        nominative = morph_places.to_nominative(raw)
        masculine = morph_places.to_nominative(morph_places.masculine_street(raw)) \
            if hasattr(morph_places, "masculine_street") else nominative
        healthy = True
        for generic, name in (("улица", nominative), ("проспект", masculine),
                              ("проспект", nominative)):
            phrase = f"{generic} {name}"
            base = place_key(phrase)
            if any(place_key(morph_places.inflect_place(phrase, case)) != base
                   for case in _PLACE_CASES):
                healthy = False
                break
        if healthy:
            usable.append(raw)
    if len(usable) < 12:
        raise RuntimeError(
            f"only {len(usable)} fake street(s) survive their own inflection; "
            "a customer with more distinct addresses than that would get a "
            "fail-closed 5xx — widen FAKE_STREETS")
    return tuple(usable)


# РАЗРЯД НОМЕРА ДОМА — СВОЙСТВО, ПО КОТОРОМУ АГЕНТ ПРИНИМАЕТ РЕШЕНИЯ, и
# подмена, которая его меняет, меняет решение. «в дома больше ста не возим» —
# обычное правило курьерской службы, оно живёт в системном промпте заказчика, и
# настоящий дом 33 под фальшивым 157 переворачивает его: агент ОТКАЗЫВАЕТСЯ
# оформлять заказ, которого никто не отменял. На живом прогоне 07.09 это 12
# троек семьи `prompt_rule`, и в каждой плечо шлюза не сделало НИ ОДНОГО
# вызова, а восстановленный ответ противоречил сам себе — «Дом 33 — номер
# больше 100».
#
# ЦЕНА НАЗВАНА И ОНА ЗАПЛАЧЕНА СОЗНАТЕЛЬНО: разряд сообщает наблюдателю, в
# каком из трёх ведёр стоит настоящий дом, — меньше полутора бит, и меньше
# того, что уже отдаёт сохранённый год в фальшивой дате рождения. Решение
# владельца от 07.09; полный разбор в
# research/2026-09-07-property-preserving-substitutes.md.
#
# ИСЧЕРПАТЬ ЭТО НЕЛЬЗЯ. Узкий разряд — это девять номеров, но улица тянется из
# большого словаря, и уникальность даёт она; там, где улица зафиксирована
# (`_same_street_in_conversation`), `_unique_token` на середине попыток и так
# отпускает её. Пул, который заказчик может исчерпать, — это вечный 5xx, и
# этот путь такого пула не создаёт.
def _house_like(original: str) -> int:
    """Фальшивый номер дома ТОГО ЖЕ РАЗРЯДА, что настоящий."""
    house_max = ASSETS.get().fakes.house_max
    bands = ((1, 9), (10, 99), (100, house_max))
    spoken_house = morph_places.split_roles(original).get("house", "") if original else ""
    digits = re.sub(r"\D", "", morph_places.house_digits(spoken_house))
    if not digits:
        return secrets.randbelow(house_max) + 1
    real = min(int(digits[:6]), house_max)
    low, high = next(band for band in bands if real <= band[1])
    return low + secrets.randbelow(high - low + 1)


def _compose_head(street: str, generic: str) -> str:
    """Подменная улица из имени и родового слова в форме ПИШУЩЕГО.

    Один сборщик на оба входа `_fake_place` (свежая чеканка и переиспользованная
    голова) — иначе две ветки одной формы разошлись бы, как расходятся все
    вторые читалки в этом файле. Пустое родовое слово — «упоминание его не
    несло», и подмена его не дописывает: форма принадлежит тому, кто пишет.
    Marker order follows the generic: a full word leads («улица Тополиная»), an
    abbreviation leads with a dot («ул. Тополиная»), «проспект» and «бульвар»
    read naturally after the name («Тополиный проспект»), and a mention that
    named no type word gets none.
    """
    if not generic:
        return street
    full = morph_places.generic_full(generic)
    abbreviated = generic.lower() != full
    if abbreviated:
        # An abbreviation always leads and keeps the exact form written: «пр-т»
        # stays «пр-т», never «проспект» and never «пр-т.» — the hyphenated forms
        # take no trailing dot.
        return f"{generic}{'' if '-' in generic else '.'} {street}"
    if full in ("проспект", "бульвар"):
        return f"{street} {generic}"
    return f"{generic} {street}"


def _fake_place(original: str, head: str = "") -> str:
    """A place of the SAME KIND as the one it replaces, in the nominative.

    `head` is the street phrase («улица Черёмуховая») of a substitute this
    conversation already holds for the SAME real street; given, no street is
    drawn and only the numbers are — see `Vault._same_street_in_conversation`.

    Two things were wrong before, and both reached the model. The phrase was
    hardcoded dative — `улице Тополиной, 21` wherever it landed — and the kind
    was chosen at random, so a street became a settlement 15% of the time and
    «доставка на ул. Профсоюзная» came back as «Кинешме». A courier system
    validating that address rejects it, which is what the landing promises will
    not happen.

    Settlements are combinatorial, not a flat list of 25: a delivery customer
    crosses that on day one, and `_unique_token` would then exhaust and raise —
    a fail-closed 5xx on every message with a new city, permanently.
    """
    if original and not morph_places.looks_like_street(original):
        # Through `_fake_city`, so a bare city gets the gender treatment too. It
        # used to draw at random here while the city-inside-an-address branch
        # below matched gender — and a masculine «Санкт-Петербурге» replaced by a
        # feminine «Чернь» leaves the restorer guessing at the case, because the
        # feminine oblique forms collapse. That produced «Санкт-Петербурга»
        # instead of «Санкт-Петербурге» intermittently, which is exactly how an
        # unmatched pair of branches fails: only on the draws that pick the
        # wrong gender.
        return _fake_city(original)

    # MIRROR THE ORIGINAL'S PARTS. «Новосибирск, Красный проспект, 25» used to
    # come back «улица Лавандовая, 46»: the city vanished and a проспект became
    # an улица. The round trip still closed — but the model is reading a
    # different KIND of address than the sentence was built around, and a model
    # that notices a mismatch is a model that edits it. That is how gender and
    # case disagreement broke names, and it is the same failure here.
    shape = morph_places.place_shape(original) if original else {}
    generic = str(shape.get("generic") or "улица")
    gender = str(shape.get("gender") or "femn")
    if head:
        # ИМЯ ГОЛОВЫ ПЕРЕИСПОЛЬЗУЕТСЯ, А РОДОВОЕ СЛОВО ПЕРЕСОБИРАЕТСЯ В ФОРМЕ
        # ЭТОГО УПОМИНАНИЯ. `head` — подменная улица той же НАСТОЯЩЕЙ улицы, но
        # записанная в форме ДРУГОГО упоминания: клиент написал «на Тверской 7»
        # после «ул. Тверская, д. 7, корп. 2», и голова, взятая дословно,
        # приносила в новое упоминание чужое сокращение «ул.». Тогда косвенная
        # подмена приходила «на ул. Ивовой 2», а `detect_case` читает сокращение
        # как именительный — подмена в косвенном слоте (test_hard_cases).
        # Настоящая улица одна, поэтому ИМЯ общее, а тип — того, кто пишет;
        # родового слова у упоминания нет — берётся то же умолчание, что у
        # свежей чеканки («улица»), иначе две записи одной улицы разошлись бы
        # формой.
        named = [w for w in head.split() if not morph_places.is_generic_word(w)]
        street = (" ".join(named) if named else
                  morph_places.to_nominative(secrets.choice(_usable_streets(ASSETS.version))))
        head = _compose_head(morph_places.agree_with_generic(street, gender), generic)
    else:
        street = morph_places.to_nominative(secrets.choice(_usable_streets(ASSETS.version)))
        # The pool is written feminine because most generics are; reusing the
        # original's generic word means the name has to follow it.
        street = morph_places.agree_with_generic(street, gender)
        head = _compose_head(street, generic)

    out = head
    # NEVER A FAKE TOWN INSIDE AN ADDRESS. The shape may say «has a city» on a
    # predicted reading — «лугвая сто шестнадцать», a mistyped street pymorphy3
    # guesses to be a place — and the fake town drawn for it reached the
    # courier's `locality` as «Торжка» (fresh-seed v4, compare-014,
    # correction-018). The settlement is the real one or none at all.
    if shape.get("has_city"):
        settlement = _settlement_of(original)
        if settlement:
            out = f"{settlement}, {out}"
    if shape.get("has_house", True):
        # NO COMMA before the house number. With one, `_merge_places` stops at
        # the house and the flat is left outside the span — so the token we mint
        # is not the token detection returns, the re-masking guard does not
        # recognise it, and our own substitute gets masked a second time.
        # «улица Рябиновая 83, кв. 203» is detected whole; the comma version is
        # not, and it is also how people actually write it.
        out = f"{out} {_house_like(original)}"
    # ПОДЪЕЗД ЧЕКАНИТСЯ, ПОТОМУ ЧТО ИНАЧЕ ЕГО НЕЛЬЗЯ ВЕРНУТЬ. Подмена его просто
    # теряла — «улица клубная дом 160 второй подъезд» становилось «улица
    # Сиреневая 166», — и дальше ломалось не восстановление, а сам разговор:
    # схема инструмента просит `entrance`, модель в подмене подъезда НЕ ВИДИТ,
    # кладёт в поле пустоту или выдумывает число, и настоящий подъезд не
    # доезжает до диспетчера ни при каком обратном пути. 39 из 201 расхождения
    # на плече аргумента — это он.
    #
    # Порядок русский: подъезд перед квартирой. Форма — как у квартиры, через
    # запятую: «улица Рябиновая 83, подъезд 2, кв. 203» детектируется целиком,
    # а без запятой перед номером дома `_merge_places` обрывает спан.
    # КОРПУС И СТРОЕНИЕ — ТА ЖЕ ИСТОРИЯ, ЧТО И ПОДЪЕЗД. «репина тридцать пять
    # строение один» приходило моделью как «Речная, 56»: строения в подмене нет,
    # положить его в аргумент неоткуда, и до диспетчера оно не доезжает.
    return _decorate_place(out, shape, {})


def _decorate_place(out: str, shape: dict[str, object], reuse: dict[str, str]) -> str:
    """The tails a mention carries, in Russian order; a tail the substitute
    being extended already had is kept, a new one is drawn."""
    if shape.get("has_building"):
        out = f"{out}, корп. {reuse.get('building') or secrets.randbelow(12) + 1}"
    if shape.get("has_entrance"):
        out = f"{out}, подъезд {reuse.get('entrance') or secrets.randbelow(24) + 1}"
    if shape.get("has_flat"):
        out = f"{out}, кв. {reuse.get('flat') or secrets.randbelow(250) + 1}"
    return out


def _extend_place(short_token: str, original: str, shape: dict[str, object]) -> str | None:
    """The FULL substitute grown from the short one already minted for this
    place: the same head and house, a fake city in front, the tails the
    fuller mention names.

    The head and house are copied VERBATIM, which keeps the short token a
    literal substring of the full one — the property `test_short_address…`
    pins for the other direction — and makes `strip_leading_city(full)` equal
    to the short token, so a later short mention links straight back.
    """
    spans = morph_places.role_spans(short_token)
    if "house" not in spans:
        return None
    base = short_token[: spans["house"][1]]
    if not base.strip():
        return None
    out = f"{_settlement_of(original) or _fake_city(original)}, {base}"
    reuse = {role: part for role, part in morph_places.split_roles(short_token).items()
             if role in ("building", "entrance", "flat")}
    return _decorate_place(out, shape, reuse)


_INITIAL_LETTERS = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЭЮЯ"


@functools.lru_cache(maxsize=4)
def _invariant_last_names(version: str) -> tuple[str, ...]:
    """The surnames whose feminine form resolves in every case.

    Asked of morphology rather than listed, so adding a name to the leased
    `FAKE_LAST` cannot leave a stale second list behind. Empty would mean the pool
    has drifted to nothing usable, and a caller silently falling back to two words
    is how that stayed invisible before — so it is stated here instead. Keyed on
    the bundle version (a fresh lease can carry a different pool).
    """
    fakes = ASSETS.get().fakes
    usable = tuple(surname for surname in fakes.last + fakes.last_invariant
                   if morph_names.survives_round_trip(
                       morph_names.feminine_surname(surname), "femn"))
    # A FLOOR, not just non-empty. One usable name would pass a non-empty check
    # and still fail the second woman a customer names, and the failure mode is
    # a permanent 5xx rather than a worse substitute — so it is worth catching at
    # import of the pool rather than in a customer's traffic.
    if len(usable) < 12:
        raise RuntimeError(
            f"only {len(usable)} surname(s) in the fake pool have a resolvable "
            "feminine form; a customer naming more women by surname alone than "
            "that would get a fail-closed 5xx — widen FAKE_LAST_INVARIANT")
    return usable


@functools.lru_cache(maxsize=4)
def _round_trip_last_names(version: str, gender: str) -> tuple[str, ...]:
    """The surnames whose form in this gender resolves back from every case
    when it stands ALONE — the feminine invariant list, and the masculine
    entries of the pool that pass the same check."""
    if gender == "femn":
        return _invariant_last_names(version)
    fakes = ASSETS.get().fakes
    usable = tuple(s for s in fakes.last + fakes.last_invariant
                   if morph_names.survives_round_trip(s, "masc"))
    if len(usable) < 12:
        raise RuntimeError(f"only {len(usable)} masculine surname(s) survive a lone round trip — widen FAKE_LAST")
    return usable


def _fake_name(gender: str | None, shape: tuple[str, ...] = ()) -> str:
    """A fake full name that AGREES WITH ITSELF and with the real person.

    `Екатерина Цветков` and `Руслан Хвостова` are not cosmetic defects: a model
    reading a disagreeing name repairs it, and a repaired token no longer
    matches the vault, so the customer's tool receives a person who does not
    exist — silently. Agreement is what removes the model's motive to touch it.

    An unknown gender picks one at random rather than defaulting to masculine,
    so the choice cannot systematically mis-gender the half of the population a
    default would.
    """
    resolved = gender if gender in ("masc", "femn") else secrets.choice(("masc", "femn"))
    # Mirror the ORIGINAL's arrangement. A three-part name replaced by a
    # two-part one changes the word count the surrounding sentence was built
    # around, and a model that notices the mismatch is a model that rewrites the
    # token — the same failure gender and case disagreement produce, on a third
    # axis. An empty shape keeps the historical «given surname».
    plan = shape or ("name", "surn")
    names = ASSETS.get().names
    patronymics = (names.patronymics_masc if resolved == "masc"
                   else names.patronymics_femn)
    for _ in range(12):
        # EVERY slot draws independently. Sharing one draw across slots of the
        # same kind produced «Иван Иван» for a two-given-name shape and
        # «Лебедева Лебедева» for a two-surname one — the latter cannot survive
        # its own inflection check, so the generator ran out of attempts and the
        # request failed closed. Shapes with a repeated kind are not exotic: a
        # keyboard slip inside «Екатерина» makes morphology read it as a surname.
        pool = _first_names_by_gender(ASSETS.version)[resolved]
        # A LONE FEMININE SURNAME HAS ONLY ONE WORKABLE POOL. Any -ова/-ина form
        # is syncretic and fails its own round trip, so drawing from the whole
        # list and hoping is not a strategy — it is 12 retries that usually work
        # and sometimes silently produce a two-word name instead. The subset is
        # DERIVED, not a second list, so it cannot drift out of step with the
        # first (the same reason `feminine_surname` derives rather than stores).
        # …AND THE MASCULINE HALF NEEDS THE SAME CHECK. A masculine surname
        # that failed its lone round trip twelve times fell through to «Имя
        # Фамилия», and the CRM card's `last_name` leaf was shown a two-word
        # person (live v4, chain-014).
        surnames = (_round_trip_last_names(ASSETS.version, resolved)
                    if plan == ("surn",) else ASSETS.get().fakes.last)
        parts: list[str] = []
        for slot in plan:
            if slot == "surn":
                surname = secrets.choice(surnames)
                parts.append(morph_names.feminine_surname(surname)
                             if resolved == "femn" else surname)
            elif slot == "patr":
                parts.append(secrets.choice(patronymics))
            elif slot == "init":
                # An initial stands for a name we are not told; a letter is the
                # whole of the information, so a letter is the whole of the fake.
                parts.append(secrets.choice(_INITIAL_LETTERS) + ".")
            else:
                parts.append(secrets.choice(pool))
        candidate = " ".join(parts)
        # The round-trip check runs on the DECLINABLE part only: initials have no
        # paradigm, and a name that is nothing but initials cannot fail one.
        checkable = " ".join(part for part, slot in zip(parts, plan) if slot != "init")
        if not checkable or morph_names.survives_round_trip(checkable, resolved):
            return candidate
    # SHAPE IS QUALITY, A TOKEN IS CORRECTNESS. Some shapes cannot be produced
    # at all — «Морозова Екатeрина», where a keyboard slip makes morphology read
    # both words as surnames, asks for two surnames in a row, and no pair of them
    # survives its own inflection. Refusing there would turn a cosmetic limit
    # into a fail-closed 5xx on a message the customer legitimately sent.
    #
    # So fall back to the shape we can always build, and only refuse if THAT
    # fails — which really would mean the pool has drifted.
    if plan != ("name", "surn"):
        return _fake_name(gender, ("name", "surn"))
    raise RuntimeError("no fake name survived its own inflection round trip")


def _shares_a_word(token: str, original: str) -> str:
    """Whether the substitute repeats any word of the original.

    Compared on the nominative, so `Марии` and `Мария` count as the same word —
    a token that differs only by inflection is not a substitution either.
    """
    def words(value: str) -> set[str]:
        out = set()
        for part in value.split():
            # AN INITIAL IS NOT A WORD. A single letter (optionally dotted)
            # stands for a name we are not told, and «Котова С. Л.» for
            # «Ващенко Т. С.» shares the letter «С» by pure chance — one letter
            # of thirty-three reveals nothing, and treating it as a shared word
            # would refuse the initials reuse this file mints on purpose
            # (`_initials_reuse`). Only a full word can leak the value it
            # replaces.
            if len(part.strip(".")) <= 1:
                continue
            out.add(part.casefold())
            try:
                out.add(morph_names.to_nominative(part).casefold())
            except Exception:  # noqa: BLE001 - morphology must not break minting
                pass
        return out
    return bool(words(token) & words(original))


def _fake_secret(original: str) -> str:
    """A credential of the same shape whose body is random.

    The VENDOR PREFIX survives and the body does not. The model reasons about
    which key to use for which call ("use the Anthropic one here"), so changing
    `sk-ant-` into `ghp_` changes the meaning of the sentence; changing the body
    changes nothing the model needs.

    Character CLASS is preserved per position — digit stays digit, upper stays
    upper — so a substitute passes the same shape checks the real key would. The
    same reasoning as the format-preserving document tokens: a fake that fails
    the customer's own validator breaks the tool call this product exists to keep
    working.

    A collision with a real credential is not possible in practice: the body is
    CSPRNG output over the key's own alphabet, and these keys carry well over a
    hundred bits. This is the credential analogue of the checksum-INVALID ID
    tokens and the reserved IP range — the token cannot name a real thing.
    """
    if original.startswith("-----BEGIN"):
        # A PEM block: keep the header and footer lines, replace the material.
        lines = original.splitlines()
        if len(lines) < 3:
            return original
        body = [
            "".join(secrets.choice(string.ascii_letters + string.digits + "+/")
                    for _ in range(len(line)))
            for line in lines[1:-1]
        ]
        return "\n".join([lines[0], *body, lines[-1]])

    prefix = credentials.secret_prefix(original)
    tail = original[len(prefix):]
    out: list[str] = []
    for char in tail:
        if char.isdigit():
            out.append(secrets.choice(string.digits))
        elif char.isupper():
            out.append(secrets.choice(string.ascii_uppercase))
        elif char.islower():
            out.append(secrets.choice(string.ascii_lowercase))
        else:
            out.append(char)  # separators keep the shape readable
    return prefix + "".join(out)


def _corresponding_part(mention: str, full_canonical: str, full_token: str) -> str | None:
    """The word of `full_token` standing in the same slot as `mention`.

    Position alone is not enough — «Иванов Пётр» and «Пётр Иванов» are the same
    person written in two orders — so the slot is found by KIND (surname, given
    name, patronymic) and looked up by kind on the substitute side.
    """
    # POSITION, BY CONSTRUCTION. The substitute is minted slot by slot in the
    # ORDER of the real name (`_fake_name(gender, shape)` mirrors it), so the
    # word standing where the mention stands is the answer, whatever the two
    # orders of «Иванов Пётр» / «Пётр Иванов» — the mention is found in the
    # CANONICAL, not in the sentence. Reading the fake's kinds with morphology
    # was the defect: «Мещерякова» has no dictionary reading and came back as
    # a given name, so the CRM card's «Ирина» was linked to «Мещерякова», its
    # «Лебедева» found no surname slot and minted «Белых», and the agent's
    # `last_name` then restored to «Ирина» (fresh-seed v4, chain-001).
    real_parts = full_canonical.split()
    fake_parts = full_token.split()
    if len(real_parts) != len(fake_parts):
        return None
    lowered = mention.casefold()
    for index, part in enumerate(real_parts):
        if part.casefold() == lowered:
            return fake_parts[index]
    return None


def _render_token(entity_type: str, gender: str | None = None,
                  original: str = "", head: str = "") -> str:
    # Format-preserving substitutes for the document types. Without these they
    # fall through to REDACTED… — which is NOT the shape the customer's own
    # validator expects, so a masked account number would fail their form check
    # and break the very tool call the product exists to keep working.
    if entity_type == "OMS":
        return _rand_digits(16)
    if entity_type == "ACCOUNT":
        return "40817810" + _rand_digits(12)
    if entity_type in ("DRIVER_LICENSE", "VEHICLE_DOC"):
        return f"{_rand_digits(2)} {_rand_digits(2)} {_rand_digits(6)}"
    if entity_type == "INTL_PASSPORT":
        return _rand_digits(9)
    if entity_type == "OGRN":
        return _fake_ogrn(13)
    if entity_type == "PLATE":
        letters = "АВЕКМНОРСТУХ"
        return (secrets.choice(letters) + _rand_digits(3)
                + "".join(secrets.choice(letters) for _ in range(2)) + _rand_digits(3))
    if entity_type == "IP":
        # 198.18.0.0/15 is the RFC 2544 benchmarking range: reserved, must never
        # appear on the public internet, so a token can never address a real host.
        # Chosen over the RFC 5737 documentation /24 it replaced for size alone —
        # that range holds 254 addresses, and the 255th distinct IP a customer
        # logged became an unmintable token and a permanent 5xx.
        return (f"198.{secrets.choice((18, 19))}."
                f"{secrets.randbelow(256)}.{secrets.randbelow(254) + 1}")
    if entity_type == "BIRTH_CERT":
        roman = secrets.choice(("I", "II", "III", "IV", "V", "VI"))
        cyr = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ"
        return f"{roman}-{secrets.choice(cyr)}{secrets.choice(cyr)} №{_rand_digits(6)}"
    if entity_type == "PHONE":
        return _fake_phone()
    if entity_type == "EMAIL":
        return "".join(secrets.choice(string.ascii_lowercase) for _ in range(8)) + "@example.ru"
    if entity_type == "SNILS":
        return _fake_snils()
    if entity_type == "INN":
        return _fake_inn(original)
    if entity_type == "CARD":
        # THE IDENTITY'S LENGTH, read from the parsed value: a card dictated
        # aloud has no digit in its text at all. Same rule as the ИНН above.
        return _fake_card(_card_length(original))
    if entity_type == "PASSPORT":
        # Series «00YY»: no ОКАТО region is 00, the year digits stay plausible
        # (blanks of 1997–2026), the format check passes, and no person can
        # hold it. See the note above `_fake_inn`.
        year = 1997 + secrets.randbelow(30)
        # …but never the blank year 2000: a series «00 00» is the placeholder
        # shape the credential rules refuse, and the agent's `series` field
        # then came back as the fake (fresh-seed v4, decompose-006).
        if year == 2000:
            year = 2001
        return f"00 {year % 100:02d} {_rand_digits(6)}"
    if entity_type in ("DATE", "DOB"):
        # DOB WAS FALLING THROUGH TO REDACTED…, and it only started to matter
        # when DOB became a type of its own: recall went 22.2% -> 82.8% the same
        # day, so every date of birth the engine now finds reached the model as
        # «REDACTED8be7d1» in a field the customer's own schema types as a date.
        # That is the failure the block at the top of this function describes —
        # a masked value their validator rejects — and it arrives on the leg
        # where a model is most tempted to «repair» what it was given.
        return _fake_date(original)
    if entity_type == "NAME":
        return _fake_name(gender, morph_names.name_shape(original) if original else ())
    if entity_type == "MAC":
        # 02: sets the locally-administered bit, so the address can never belong
        # to a vendor OUI — the MAC analogue of the reserved IP range.
        return "02:" + ":".join(f"{secrets.randbelow(256):02X}" for _ in range(5))
    if entity_type == "VIN":
        # Deliberately built to FAIL its own check digit, like the fake СНИЛС and
        # ИНН: a token must never name a real vehicle.
        alphabet = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
        body = "".join(secrets.choice(alphabet) for _ in range(17))
        wrong = next(c for c in "0123456789X" if c != body[8])
        return body[:8] + wrong + body[9:]
    if entity_type == "SECRET":
        return _fake_secret(original)
    if entity_type == "LOC":
        return _fake_place(original, head)
    return f"REDACTED{secrets.token_hex(3)}"


# Shapes of every token _render_token can mint, most specific first (Python's
# alternation is leftmost-FIRST, not longest, so CARD must precede the bare
# 10-digit INN or a card would be resolved as an INN prefix).
#
# INVARIANT: every value _render_token returns MUST match this pattern.
# unmask_text finds candidates by shape instead of scanning the whole vault, so a
# token shape that escaped this pattern would silently stop being reversible —
# and on the response leg that means a tool executes on a FAKE value, which is
# worse than a miss. test_product.py::test_token_shapes asserts the invariant for
# every entity type; add the shape here when you add a type to _render_token.
def _stem(word: str) -> str:
    """The invariant head of a street-type word, for matching any of its forms.

    Trailing vowels and the soft sign go, because those are the characters case
    endings replace; at least four characters stay, so a stem can never be short
    enough to match an unrelated word.
    """
    stem = word
    while len(stem) > 4 and stem[-1] in "аеёиоуыэюяьй":
        stem = stem[:-1]
    return re.escape(stem)


def _city_stem(word: str) -> str:
    """The invariant head of a city name. One trailing vowel goes, no more."""
    stem = word[:-1] if len(word) > 4 and word[-1] in "аеёиоуыэюяьй" else word
    return re.escape(stem)


def _loc_token_pattern() -> str:
    """Every address shape the generator can produce, in one alternative."""
    full, short = morph_places.generic_forms()
    # STEMS, not whole words. The same pattern has to find tokens in the model's
    # reply, and Russian inflection changes the ending: «улица» becomes «улицу»,
    # «улицы», «улице». Appending a tail to the nominative does not match any of
    # them, because the nominative's own final vowel is what got replaced.
    generics = "|".join(_stem(word) + r"\w{0,4}"
                        for word in sorted(full, key=len, reverse=True))
    abbrs = "|".join(re.escape(word) for word in sorted(short, key=len, reverse=True))
    name = r"[А-ЯЁ][а-яё]+"
    # The case flag is SCOPED to the generic words. Applying `(?i)` to the whole
    # pattern turns `[А-ЯЁ][а-яё]+` into "any word" — the same mistake documented
    # for the address recogniser, and it made the restoration window swallow
    # ordinary prose around the token.
    head = (rf"(?:(?i:{generics})\s{name}"         # улица Тополиная
            rf"|{name}\s(?i:{generics})"           # Тополиный проспект
            # ЛЕВАЯ ГРАНИЦА У СОКРАЩЕНИЯ ОБЯЗАТЕЛЬНА. Без неё «ул» находится
            # ВНУТРИ слова: «Барнаул Ивовая 55» давало окно «ул Ивовая 55» со
            # смещения 5, и восстановление подставляло настоящую улицу прямо в
            # середину названия города — «Барнаонватаняна 50». Запятая после
            # города пряталa дефект, потому что подмена чеканилась с ней;
            # клиент, написавший город без запятой, его вскрывает. Дефис в
            # классе — чтобы «-ул» дефисного названия тоже не открывало окно.
            rf"|(?<![А-Яа-яЁёA-Za-z-])(?i:{abbrs})\.?\s{name}"   # ул. Тополиная
            # СОКРАЩЕНИЕ СТОИТ И ПОСЛЕ ИМЕНИ. «Луговой просп., 129» — модель
            # сократила родовое слово в форме «имя + тип», а эта ветка была
            # только у полных слов, поэтому окно не строилось вовсе и адрес
            # уходил в инструмент подменой. Мы такую форму не чеканим; здесь
            # речь о том, что модель могла НАПИСАТЬ.
            rf"|{name}\s(?i:{abbrs})\.?)")         # Тополиная ул.
    # Cities inflect too — «Сортавала» is written «Сортавалу» after «в». The
    # nominative literal matched neither, so the city-prefixed alternative never
    # fired, the head-only one did, and its key (no city) missed the stored key
    # (with city). Same stem treatment as the generics; the mandatory «, » that
    # follows a city in a minted token is what keeps a short stem from running
    # into an unrelated word.
    # ANY settlement, not the fake pool: the city in a minted token is the
    # customer's own (`_settlement_of`), one or two capitalised words, and it
    # inflects with the sentence — «в Самаре, на улице …». The mandatory «, »
    # after it is what keeps an unrelated capitalised word out.
    city = r"[А-ЯЁ][а-яё-]+(?:\s[А-ЯЁ][а-яё-]+)?"
    # The house number is written without a comma now, but tokens minted
    # BEFORE that change are in customers' vaults and still have to be
    # recognised in a reply — so both separators are accepted.
    # ПОДЪЕЗД СТОИТ МЕЖДУ ДОМОМ И КВАРТИРОЙ, и добавить его в чеканку, забыв
    # добавить сюда, значит отчеканить подмену, которую восстановитель не узнаёт:
    # измерено, аргумент падал с 87.7% до 65.0%, а `not_resolved` рос с 45 до 433.
    # Шаблон описывает то, что мы чеканим, и живёт в одном коммите с генератором.
    # ДОМ МОЖЕТ НЕСТИ СВОЙ МАРКЕР «д.»/«дом». Подмена теперь показывается в форме
    # клиента (`redact._token_for_text`: строчными, слитно, без запятых, как он
    # написал), и модель-переписчик приводит её к своей — «улица Рябиновая д. 24
    # кв. 180». Без «д.» здесь окно обрывалось на названии улицы, дом и квартира
    # уходили подменой в инструмент (замерено на публичном rewriter-агенте). Дом
    # клиент почти всегда пишет без слова, но модель его дописывает — обе формы
    # тут и восстанавливаются.
    return (rf"(?:(?:{city}), )?{head}(?:,? (?:(?i:дом|д)\.? ?)?\d{{1,3}})?"
            rf"(?:,? (?i:корп|кор|стр|строение|литер)\.? ?\d{{1,3}})?"
            rf"(?:,? (?i:подъезд|под)\.? ?\d{{1,3}})?(?:,? кв\.? ?\d{{1,3}})?")


LOC_TOKEN_PATTERN = _loc_token_pattern()

# Where the question «is this string our own substitute?» is asked. Named here
# so the two entry points, the vault and the docs use ONE spelling of each.
PSEUDONYM_SCOPES = ("conversation", "customer")

@functools.lru_cache(maxsize=4)
def _token_re(version: str) -> re.Pattern[str]:
    """The token-recognition alternation, keyed on the bundle version: NAME is
    anchored on the leased FAKE_FIRST pool and LOC(city) on FAKE_CITIES, so the
    regex rebuilds when a fresh lease carries a different pool (and unload clears
    it). Everything else is fixed shape."""
    fakes = ASSETS.get().fakes
    return re.compile("|".join([
        # EMAIL, IN ANY LETTER CASE: an agent that upper-cases a field wrote
        # «HUTHDHTQ@EXAMPLE.RU» and the token was never a candidate, so the
        # fake reached the tool. The lookup folds it; the real address comes
        # back in the agent's case.
        r"(?i:[a-z]{8}@example\.ru)",                 # EMAIL
        # NAME is combinatorial, so it is anchored on the FIRST-NAME pool rather than
        # listed exhaustively or matched as "two capitalised words". The generic
        # shape was tried and is wrong: scanning left to right, `Клиент Мирослава
        # Фомин` matches `Клиент Мирослава` first and the real token is never seen —
        # an unresolvable token reaching a tool, the exact failure this pattern
        # exists to prevent. Anchoring on a distinctive given name cannot drift that
        # way, and over-matching a real person with the same given name is harmless:
        # the candidate simply fails the vault lookup.
        r"\b(?:" + "|".join(fakes.first) + r") [А-ЯЁ][а-яё]+",   # NAME
        # LOC, both families. The street form carries its house number so the
        # numbered token is matched whole; without the number the vault lookup would
        # be handed a prefix that is not a key.
        # LOC. Assembled from `morph_places.generic_forms()` so it cannot fall
        # behind the generator: the substitute now MIRRORS the original's shape, so
        # there is no single street form left to hardcode — «улица Тополиная, 7»,
        # «Тополиный проспект, 7», «ул. Тополиная, 7» and any of them behind a city
        # and in front of a flat are all shapes we mint.
        #
        # The full address alternative must come FIRST: alternation is leftmost, and
        # a bare city listed earlier would match the city and stop, handing the vault
        # a prefix that is not a key.
        LOC_TOKEN_PATTERN,                                             # LOC (street)
        # \b on both sides. Without the trailing one «Одоев» matched inside the
        # inflected «Одоеве», the city was replaced and the leftover «е» stuck to the
        # restored value: «Санкт-Петербургее». It never showed while the pool was
        # stored oblique — the stored form WAS the inflected one — so moving the pool
        # to the nominative is what exposed a boundary that was always missing.
        # An inflected city now falls through to the signature path, which resolves it.
        *(rf"\b{re.escape(value)}\b" for value in fakes.cities),       # LOC (city)
        r"\d{2} \d{2} \d{6}",                        # DRIVER_LICENSE / VEHICLE_DOC / PASSPORT
        r"198\.1[89]\.\d{1,3}\.\d{1,3}",              # IP (RFC 2544 benchmarking)
        r"[IVX]{1,4}-[А-ЯЁ]{2} №\d{6}",               # BIRTH_CERT
        # BOTH ALPHABETS. A plate token has to be recognised in the model's reply
        # even when the model rewrote it in Latin — the ГОСТ alphabet exists so the
        # two readings are the same plate, and a model treats them as one string.
        # Matching only Cyrillic meant the rewritten form was never even a candidate,
        # so the fold that resolves it never got the chance to run.
        # BOTH LATIN READINGS, not just the look-alike one. The class listed the
        # letters a plate LOOKS like in Latin; a model that spells it out uses others
        # — V for «В», N for «Н», S for «С», U for «У», R for «Р». Those forms never
        # became candidates, so the fold that resolves them never ran.
        # …AND A PLATE IN LOWER CASE, for the same reason («е940ае613»).
        # …AND WITH THE SEPARATORS THE CUSTOMER WROTE. The substitute now mirrors
        # the source's notation (`notation.plate_laid_like`), so «у 493 са 23»
        # mints «х 731 кх 616» — and a shape that demands the glued form would
        # stop recognising our own token, which is the one failure this pattern
        # exists to prevent. Spaces, tabs, commas and hyphens, at most two of
        # them, are notation here; letters and digits are content.
        r"(?i:[АВЕКМНОРСТУХABCEHKMNOPRSTUVXY][ \t,\-]{0,2}\d{3}[ \t,\-]{0,2}"
        r"[АВЕКМНОРСТУХABCEHKMNOPRSTUVXY]{2}[ \t,\-]{0,2}\d{2,3})",  # PLATE, нотация клиента
        r"(?i:[АВЕКМНОРСТУХABCEHKMNOPRSTUVXY]\d{3}[АВЕКМНОРСТУХABCEHKMNOPRSTUVXY]{2}\d{2,3})",  # PLATE, ГОСТ
        # FOURS WITH THE REMAINDER LAST, 13..19 digits: the shape must cover
        # every length the generator above can mint, because a token that
        # escapes it stops being reversible and a FAKE reaches the tool. `{2,4}`
        # of the fours plus a 1..3 tail is exactly 13-19, and the sixteen-digit
        # form keeps its original spelling.
        r"\d{4}(?: \d{4}){2,4}(?: \d{1,3})?",        # CARD — 13..19, fours with the remainder last
        # Bare digit runs, LONGEST FIRST: leftmost-first alternation would otherwise
        # let \d{10} consume the head of a 20-digit account.
        r"\b\d{20}\b",                                # ACCOUNT
        r"\b\d{16}\b",                                # OMS
        r"\b\d{15}\b|\b\d{13}\b",                    # OGRN / ОГРНИП
        r"\b\d{9}\b",                                 # INTL_PASSPORT
        r"\d{3}-\d{3}-\d{3} \d{2}",                   # SNILS
        r"\d{2} \d{2} \d{6}",                         # PASSPORT
        r"\d{2}\.\d{2}\.\d{4}",                       # DATE, как минтится
        # DATE, КАК ЕЁ ПЕРЕПИШЕТ МОДЕЛЬ. A tool argument named `date` invites ISO,
        # and a model obliges: the token «02.12.1973» came back as «1973-12-02» and
        # was never even a candidate here, so the lookup that would have resolved it
        # never ran and the FAKE reached the customer's tool. Two personas hit this
        # independently on live traffic — one moved a delivery to 1973, the other
        # booked a patient into 1977.
        r"\d{4}-\d{2}-\d{2}",                           # ISO
        r"\d{2}[/-]\d{2}[/-]\d{4}",                     # 12/04/1961, 12-04-1961
        # DATE, КАК ЕЁ НАПИСАЛ КЛИЕНТ — и как её теперь чеканит подмена:
        # «15.9.82», «5.09.1982», «10/4/82». Двузначный год читается тем же
        # правилом века, что и в `_date_canonical`. Промах стоит один
        # индексный запрос; ложного попадания быть не может — строка должна
        # совпасть с канонической датой подмены этого заказчика.
        r"\b\d{1,2}([./ -])\d{1,2}\1\d{2,4}\b",         # DATE, свободная запись («15.9.82», «19 12 1992»)
        r"\+79\d{9}(?!\d)",                          # PHONE, never a numeric prefix
        r"REDACTED[0-9a-f]{6}",                       # fallback
        r"\b\d{10}\b",                                # INN — least specific, last
    ]))


def token_re() -> re.Pattern[str]:
    """The token recognizer for the CURRENT bundle. Was a module-level TOKEN_RE;
    now per-version because the fake pools that feed it are leased, not compiled."""
    return _token_re(ASSETS.version)


def _street_stem(value: str) -> str:
    """Основа названия улицы — то, что остаётся, когда убрали тип и падеж."""
    street = morph_places.split_roles(value).get("street", "")
    if not street:
        return ""
    words = [word for word in street.split()
             if not morph_places.is_generic_word(word)]
    if not words:
        return ""
    return " ".join(morph_places.to_nominative(word).casefold().replace("ё", "е")
                    for word in words)


def create_tables(conn: Connection) -> None:
    """The base tables of the vault — `CREATE … IF NOT EXISTS`, every open.
    Columns the STEPS added are not here: a fresh store gets them from the steps,
    the same way every existing volume did."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS tokens ("
        "customer TEXT, canonical TEXT, entity_type TEXT, token TEXT, "
        "PRIMARY KEY (customer, canonical))"
    )
    # Which words each NAME row is made of, so a later partial mention can
    # find its person by an indexed point query instead of a table scan.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS name_parts ("
        "customer TEXT, part TEXT, canonical TEXT, "
        "PRIMARY KEY (customer, part, canonical))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_name_parts ON name_parts (customer, part)"

    )
    conn.execute(
        # PARTS OF THE SUBSTITUTE, mirroring `name_parts` for the real value.
        # `name_parts` answers «have we met this person»; this answers «is
        # this string still one of ours». A model that reorders or shortens a
        # fake produces a string that resolves to nothing, and without this
        # the gateway cannot tell that from an ordinary sentence — which is
        # why the failure was silent and every persona asked for a signal.
        "CREATE TABLE IF NOT EXISTS token_parts ("
        "customer TEXT NOT NULL, part TEXT NOT NULL, token TEXT NOT NULL, "
        "PRIMARY KEY (customer, part, token))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_token_parts ON token_parts (customer, part)"
    )
    conn.execute(
        # WHICH FULL ADDRESSES A SHORT MENTION COULD BE, SCOPED TO ONE
        # CONVERSATION. `name_parts` answers the same question for people
        # and is scoped to the customer, which is right there: a person's
        # name is distinctive enough that the single-candidate rule still
        # fires. A street is not — «Ленина 14» exists in every Russian city,
        # so at customer scope the rule would find a dozen owners and refuse
        # every time. The conversation is where the question has an answer.
        #
        # No new class of data: `part` is a street stem and a house number,
        # both already stored in full in `tokens.canonical`.
        "CREATE TABLE IF NOT EXISTS place_parts ("
        "customer TEXT NOT NULL, conversation TEXT NOT NULL, "
        "part TEXT NOT NULL, canonical TEXT NOT NULL, "
        "created REAL NOT NULL DEFAULT 0, "
        "has_city INTEGER NOT NULL DEFAULT 1, "
        "PRIMARY KEY (customer, conversation, part, canonical))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_place_parts "
        "ON place_parts (customer, conversation, part)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_place_parts_created "
        "ON place_parts (created)"
    )
    # WHICH NAME SUBSTITUTES THIS CONVERSATION WAS SHOWN. A piece of a
    # substitute («Николая» for «Николай Крылов») can only come back from the
    # dialogue that saw the whole; resolved against the customer's WHOLE
    # vault, the customer's own word «николая» inside «улица Николая
    # Заболоцкого» became another person (known-issues Б23). `minted_in` names
    # the first dialogue only; a token reused by a later one is recorded here.
    # Expires with `place_parts`, for the same reason: it is a record of who
    # was talked about when. No new class of data — the token is already in
    # `tokens`, the conversation in `minted_in`.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS token_uses ("
        "customer TEXT NOT NULL, token TEXT NOT NULL, conversation TEXT NOT NULL, "
        "created REAL NOT NULL DEFAULT 0, "
        "PRIMARY KEY (customer, token, conversation))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_token_uses_created ON token_uses (created)"
    )
    # WHAT THIS CONVERSATION WAS SHOWN IN PLACE OF WHAT THE CUSTOMER WROTE —
    # character for character, on both sides. An agent that copies the shown
    # form verbatim gets the customer's literal string back: the Latin «a»
    # inside «бaбичев», the Cyrillic «О» inside «682О 8116», the address with
    # no street word — exactly what it would have passed without us. Rebuilt
    # forms (case, notation, grouping) are for the agent that rewrote the
    # substitute. One row per shown form per conversation; expires with
    # `place_parts`. The literal is the same class of data as
    # `tokens.original`, under the same key.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS shown_forms ("
        "customer TEXT NOT NULL, conversation TEXT NOT NULL, shown TEXT NOT NULL, "
        "original TEXT NOT NULL, entity_type TEXT NOT NULL, "
        "created REAL NOT NULL DEFAULT 0, "
        "PRIMARY KEY (customer, conversation, shown))"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_shown_forms_created ON shown_forms (created)"
    )


def create_indexes(conn: Connection) -> None:
    """Indexes over columns the steps added; runs after them, every open."""
    # Every lookup on the response leg is an indexed point query, so
    # detokenization cost tracks the length of the answer, not the size of
    # the vault. Without these indexes each one degrades to a table scan.
    for statement in (
        "CREATE INDEX IF NOT EXISTS idx_tokens_token ON tokens (customer, token)",
        "CREATE INDEX IF NOT EXISTS idx_tokens_digits ON tokens (customer, digits)",
        "CREATE INDEX IF NOT EXISTS idx_tokens_digits10 ON tokens (customer, digits10)",
        "CREATE INDEX IF NOT EXISTS idx_tokens_namekey ON tokens (customer, name_key)",
    ):
        conn.execute(statement)


def _migrate_digit_signatures(conn: Connection) -> None:
    """Add + backfill the digit-signature columns used to resolve a numeric
    token the model REFORMATTED. Previously this index was rebuilt from every
    row of the vault on every single response; storing the signature makes it
    an indexed lookup instead."""
    columns = [row[1] for row in conn.execute("PRAGMA table_info(tokens)").fetchall()]
    if "digits" in columns:
        return
    conn.execute("ALTER TABLE tokens ADD COLUMN digits TEXT")
    conn.execute("ALTER TABLE tokens ADD COLUMN digits10 TEXT")
    rows = conn.execute(
        "SELECT customer, canonical, token, entity_type FROM tokens"
    ).fetchall()
    for customer, canonical, token, entity_type in rows:
        digits, digits10 = _digit_signatures(token, entity_type)
        conn.execute(
            "UPDATE tokens SET digits=?, digits10=? WHERE customer=? AND canonical=?",
            (digits, digits10, customer, canonical),
        )


def _migrate_name_keys(conn: Connection) -> None:
    """Add the case-invariant signature of a NAME token.

    The exact counterpart of `digits` for phone numbers, and it exists for
    the same reason. A phone the model reformatted (+7 -> 8, separators
    dropped) no longer matches its minted shape, so it is resolved by digit
    signature instead; a NAME the model INFLECTED (`Руслану Хвостову`) no
    longer matches either, and until now nothing caught it — the fake went
    straight into the customer's tool.

    Backfilled for existing rows so a vault created before this migration
    gains the protection without being rebuilt.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(tokens)")}
    if "name_key" in columns:
        return
    conn.execute("ALTER TABLE tokens ADD COLUMN name_key TEXT")
    rows = conn.execute(
        "SELECT customer, canonical, token FROM tokens WHERE entity_type='NAME'"
    ).fetchall()
    for customer, canonical, token in rows:
        conn.execute(
            "UPDATE tokens SET name_key=? WHERE customer=? AND canonical=?",
            (name_key(token), customer, canonical),
        )
    conn.commit()


def _migrate_original_form(conn: Connection) -> None:
    """Add the surface form the value was FIRST seen in.

    Canonicalization must stay, but only as the dedup key: it is what makes
    `+7 999 123-45-67` and `89991234567` resolve to one token, so the model
    sees one identity. What the TOOL receives is a different question, and
    returning the canonical form was an observable behaviour change we
    imposed — without Pseudex the tool would have received exactly what the
    user typed. A CRM that matches phone numbers as strings would silently
    fail to find the record. So the original is stored and returned; a caller
    that wants a normalized form can normalize it itself.

    Backfill sets original = canonical: for pre-existing rows the surface form
    was never recorded and canonical is the only truth available."""
    columns = [row[1] for row in conn.execute("PRAGMA table_info(tokens)").fetchall()]
    if "original" in columns:
        return
    conn.execute("ALTER TABLE tokens ADD COLUMN original TEXT")
    conn.execute("UPDATE tokens SET original = canonical WHERE original IS NULL")


def _migrate_first_seen(conn: Connection) -> None:
    """When each value was FIRST protected — the billing meter.

    Added because the meter we had counted the wrong thing. Audit events
    record a cache MISS, so one phone number appearing in four different
    messages counted as three "protected values" — and the count moved with
    `PSEUDEX_MASK_CACHE_SIZE` (a customer could lower their own bill with an
    env var) and with the worker count (each worker holds its own cache, so
    the same traffic cost more on a bigger container).

    A row here is one distinct real value for one customer, forever. Counting
    rows created inside a period answers "how many new people's data did we
    protect this month", which is what the invoice line actually claims and
    the only number the customer can check against their own vault.

    Existing rows get the migration time. Pre-launch there are none, and
    NULL would silently drop them out of every period.
    """
    columns = [row[1] for row in
               conn.execute("PRAGMA table_info(tokens)").fetchall()]
    if "first_seen" in columns:
        return
    conn.execute("ALTER TABLE tokens ADD COLUMN first_seen REAL")
    conn.execute("UPDATE tokens SET first_seen=? WHERE first_seen IS NULL",
                       (time.time(),))
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tokens_first_seen ON tokens (first_seen)")
    conn.commit()


def _migrate_place_created(conn: Connection) -> None:
    """Add the sweep timestamp to a `place_parts` table written before it.

    The table itself is new, but a developer volume from earlier today has
    rows without the column, and without it the sweep would raise on every
    insert — turning a housekeeping detail into a fail-closed 5xx on every
    message carrying an address.
    """
    columns = [row[1] for row in
               conn.execute("PRAGMA table_info(place_parts)").fetchall()]
    if "created" in columns:
        return
    conn.execute(
        "ALTER TABLE place_parts ADD COLUMN created REAL NOT NULL DEFAULT 0")
    conn.execute("UPDATE place_parts SET created=? WHERE created=0",
                       (time.time(),))
    conn.commit()


def _migrate_place_has_city(conn: Connection) -> None:
    """Whether the indexed address named a city. Rows written before the
    column were city-bearing by construction, so the default is 1."""
    columns = [row[1] for row in
               conn.execute("PRAGMA table_info(place_parts)").fetchall()]
    if "has_city" in columns:
        return
    conn.execute(
        "ALTER TABLE place_parts ADD COLUMN has_city INTEGER NOT NULL DEFAULT 1")
    conn.commit()


def _migrate_fold_key(conn: Connection) -> None:
    """Add the case/ё-insensitive lookup signature to existing vaults.

    Backfilled in place: a customer's rows are their people, and rekeying
    them would be a rewrite of the thing the product exists to keep stable.
    The column is additive and the exact-canonical lookup still runs first,
    so a vault that has not been migrated yet behaves exactly as before.
    """
    columns = [row[1] for row in
               conn.execute("PRAGMA table_info(tokens)").fetchall()]
    if "canonical_fold" in columns:
        return
    conn.execute("ALTER TABLE tokens ADD COLUMN canonical_fold TEXT")
    rows = conn.execute(
        "SELECT customer, canonical FROM tokens").fetchall()
    conn.executemany(
        "UPDATE tokens SET canonical_fold=? WHERE customer=? AND canonical=?",
        [(fold_key(canonical), customer, canonical) for customer, canonical in rows])
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tokens_fold "
        "ON tokens (customer, canonical_fold)")
    conn.commit()


def _migrate_minted_in(conn: Connection) -> None:
    """Which conversation each substitute was born in.

    THE RE-MASKING GUARD NEEDS A SCOPE OR IT IS A LEAK. `is_minted_token`
    asks «is this string one of ours», and answers yes for a REAL person who
    happens to bear a name we minted for somebody else — measured at 2 to 3
    people per 3000 on NEREL, every one of them sent to the model in the
    clear, for ever, because the answer does not change on the next turn.

    A conversation is what separates the two readings. Our own token comes
    back to us inside the dialogue it was minted in; a customer's contact who
    happens to be called that arrives in some other one. Scoping the guard
    keeps the echo case (which is what it was built for) and masks the
    stranger.

    EXISTING ROWS KEEP THE OLD BEHAVIOUR. A NULL here means «minted before we
    recorded this», and the guard treats it as matching any conversation —
    a vault that has not been migrated behaves exactly as it did, which is
    the same rule every other migration in this file follows.
    """
    columns = [row[1] for row in
               conn.execute("PRAGMA table_info(tokens)").fetchall()]
    if "minted_in" not in columns:
        conn.execute("ALTER TABLE tokens ADD COLUMN minted_in TEXT")
        conn.commit()


def _migrate_extends(conn: Connection) -> None:
    """Which substitute this one was grown from — the short mention's token
    for a full address, the two-word name's for a three-word one. NULL for
    every row minted before the column and for every fresh mint; the chain
    is what lets a fragment resolve when two tokens share its parts."""
    columns = [row[1] for row in
               conn.execute("PRAGMA table_info(tokens)").fetchall()]
    if "extends" not in columns:
        conn.execute("ALTER TABLE tokens ADD COLUMN extends TEXT")
        conn.commit()


# THE NUMBERED HISTORY OF THE VAULT (D-058). Order is the order the constructor
# used to call them in, and it is load-bearing twice: `create_indexes` needs
# the columns of steps 1 and 2, and `test_schema.py` pins the numbers so a
# reordering cannot renumber what an existing volume was stamped with. Every
# step is idempotent — it checks `PRAGMA table_info` first — because for a year
# they all ran on every open; that is what lets a pre-versioned volume (0) run
# all of them and be stamped. `introduced` is the engine version that first
# shipped the step; all nine predate the numbering and say 0.3.0.
VAULT_MIGRATIONS: tuple[schema.Step, ...] = (
    schema.Step(1, "digit_signatures", "0.3.0", _migrate_digit_signatures),
    schema.Step(2, "name_keys", "0.3.0", _migrate_name_keys),
    schema.Step(3, "original_form", "0.3.0", _migrate_original_form),
    schema.Step(4, "first_seen", "0.3.0", _migrate_first_seen),
    schema.Step(5, "place_created", "0.3.0", _migrate_place_created),
    schema.Step(6, "place_has_city", "0.3.0", _migrate_place_has_city),
    schema.Step(7, "fold_key", "0.3.0", _migrate_fold_key),
    schema.Step(8, "minted_in", "0.3.0", _migrate_minted_in),
    schema.Step(9, "extends", "0.3.0", _migrate_extends),
)


class Vault:
    """Persistent per-customer token store (external state -> class)."""

    def __init__(self, db_path: str, customer_id: str) -> None:
        self._customer = customer_id
        # THE CONVERSATION THIS VIEW IS SCOPED TO, empty when there is none.
        # Not a constructor argument: the Vault is built once per org and cached,
        # while a conversation lives for one request. `for_conversation` hands
        # out a view instead — see there for why the scope has to exist at all.
        self._conversation = ""
        # WHOSE SUBSTITUTE THIS IS, asked at conversation scope by default. See
        # `with_pseudonym_scope` for the one reason a host widens it (agent
        # memory) and for the price of widening.
        self._pseudonym_scope = "conversation"
        # Пусто по умолчанию: пока хост не объявил своих значений, ни одна
        # проверка ниже ничего не меняет. См. `with_own_values`.
        self._own_keys: frozenset[str] = frozenset()
        # ЦИФРОВЫЕ ПОДПИСИ ПОДМЕН, НАПИСАННЫХ АГЕНТОМ В ЭТОМ ВЫЗОВЕ ЦЕЛИКОМ.
        # Пусто по умолчанию: пока вызывающий не посчитал их по тексту вызова,
        # ни одна проверка ниже ничего не меняет. См. `with_spent_signatures`.
        self._spent_signatures: frozenset[str] = frozenset()
        # ЧИСЛА, НАПИСАННЫЕ АГЕНТОМ В ЭТОМ ВЫЗОВЕ, — то, чем кусок пришит к
        # целой подмене за пределами разговора. Пусто по умолчанию, как и
        # разговор: без них кусок спрашивается только внутри разговора.
        # См. `with_written_digits`.
        self._written_digits: tuple[str, ...] = ()
        self._lock = threading.Lock()
        self._conn = sqlite_connect(db_path, VAULT_STORE)
        # Base tables, numbered steps, indexes over migrated columns — and the
        # refusals: a volume stamped above what this image knows is not opened
        # (D-058). Once per volume in `PSEUDEX_ROLE=migrate`; here every worker
        # takes the fast path. See pseudex/schema.py.
        schema.ensure(self._conn, VAULT_STORE, db_path)

    def _unique_token(self, entity_type: str, gender: str | None = None,
                      original: str = "", canonical: str = "", head: str = "") -> str:
        """Mint a token not already used for this customer.

        BOUNDED on purpose. This used to loop until it found a free token, which
        turned an exhausted pool into an unbounded hang on the request path — the
        flat five-name list meant the sixth distinct person in an org spun here
        forever. The pool is combinatorial now, but a bound still belongs here: a
        loud failure is recoverable, a hung request is not, and in a fail-closed
        gateway the 5xx is the correct outcome."""
        for attempt in range(_TOKEN_MINT_ATTEMPTS):
            # THE STREET THIS CONVERSATION ALREADY FAKED FOR THE SAME REAL STREET
            # is kept for the first half of the attempts; if no free numbers are
            # found beside it, the place is minted on its own as before.
            token = _render_token(entity_type, gender, original,
                                  head if attempt < _TOKEN_MINT_ATTEMPTS // 2 else "")
            # The settlement pool is a flat 25 names with no combinatorial
            # dimension, so a customer past 25 distinct cities would exhaust it
            # and get a fail-closed 5xx on every message with a new one. Falling
            # back to the street shape is a mismatch in a rare case; a permanent
            # 5xx is an outage. Attempts are bounded either way.
            if entity_type == "LOC" and attempt >= _TOKEN_MINT_ATTEMPTS // 2:
                street = morph_places.to_nominative(secrets.choice(_usable_streets(ASSETS.version)))
                token = f"улица {street}, {secrets.randbelow(ASSETS.get().fakes.house_max) + 1}"
            # A substitute that shares a WORD with the value it replaces hides
            # nothing about that word. Comparing whole strings is not enough:
            # for `Мария` the token is `Мария Лебедева`, the surname differs,
            # and the real first name goes straight to the model — measured at
            # 18 collisions in 300 mints against our pool. Every check stayed
            # green, because a token WAS minted; it just did not substitute.
            # NAME only. For a LOC the generic word is shared by construction —
            # every street token contains «улица», so this check rejected every
            # candidate and the pool "exhausted" after 200 tries on the first
            # address. The rule is about a substitute repeating the PERSON it
            # replaces, which is where the collision actually leaks something.
            if not self._is_free_token(token, entity_type, original, canonical):
                continue
            # A NAME NEVER REPEATS A WORD. A foreign «тагиев рустам» reads as
            # two given names, and the two slots drew the same one — «Кирилл
            # Кирилл» — so the CSV's two cells each resolved to the whole
            # person: «тагиев рустам;тагиев рустам». One draw in a hundred.
            if entity_type == "NAME" and len(set(token.split())) != len(token.split()):
                continue
            # THE NUMBERS OF A FRESH PLACE DRAW MUST NOT CONTAIN EACH OTHER, AND
            # NONE MAY BE A NUMBER OF THE REAL VALUE. «улица Барбарисовая 1,
            # корп. 11» for «мончегорсуая 195 корпус 1» came back from prose as
            # «… корпус 195» (the house «1» found inside the building «11»),
            # and «улица Вишнёвая 1, корп. 8» for the same value wrote the real
            # house into the building (the fake house IS the real building).
            # Here and not in `_is_free_token`: a token GROWN from a short one
            # shares its numbers by construction. The real value's numbers are
            # read off its key, where a spoken «один» is already «1».
            if entity_type == "LOC" and _place_numbers_collide(token, original):
                continue
            # TWO PEOPLE IN ONE DIALOGUE MAY NOT SHARE A FAKE SURNAME. With 28
            # surnames in the pool, a message naming two people drew the same
            # one for both once in 28 times — «Шилов Семён» and «Шилова Иванна»
            # — and the CSV the agent then built carried «Шилова», which is the
            # woman's nominative AND the man's genitive: two owners, refused,
            # and the fake reached the customer's CRM. Any shared word stem is
            # refused for the first half of the attempts, and only for the first
            # half: a dialogue naming more people than the pool has surnames
            # must still be served rather than 5xx'd.
            if (entity_type == "NAME" and self._conversation
                    and attempt < _TOKEN_MINT_ATTEMPTS // 2
                    and self._shares_a_stem_in_conversation(token)):
                continue
            # …AND TWO PLACES IN ONE DIALOGUE MAY NOT SHARE A HOUSE NUMBER. A
            # corrected address («сто сорок семь … ой нет, сто девятнадцать»)
            # is two tokens, and the agent fills `building` with the house
            # alone; a house both fakes carry has two owners, is refused, and
            # the fake number reaches the courier. 2 of 300 draws.
            if (entity_type == "LOC" and self._conversation
                    and attempt < _TOKEN_MINT_ATTEMPTS // 2
                    and self._shares_a_house_in_conversation(token)):
                continue
            # …AND TWO DIFFERENT REAL STREETS MAY NOT SHARE A FAKE ONE. The
            # inverse rule — one real street, one fake street — is deliberate
            # (`_same_street_in_conversation`) and is what `head` carries; this
            # is the direction nothing guarded. «заречная 57 … энгельса 106»
            # drew «Вишнёвая» twice about one draw in six, and then a bare
            # street written by the agent has two owners, is refused, and OUR
            # street reaches the customer's system. Skipped when `head` asked
            # for the reuse, and only for the first half of the attempts, so a
            # dialogue naming more streets than the pool holds is still served.
            if (entity_type == "LOC" and self._conversation
                    and attempt < _TOKEN_MINT_ATTEMPTS // 2
                    and not (head and _street_stem(token) == _street_stem(head))
                    and self._shares_a_street_in_conversation(token)):
                continue
            return token
        raise RuntimeError(
            f"exhausted the {entity_type} token pool for customer "
            f"{self._customer!r} after {_TOKEN_MINT_ATTEMPTS} attempts — widen "
            f"the pool in _render_token"
        )

    def _shares_a_stem_in_conversation(self, token: str) -> bool:
        """Whether any word of the candidate shares its stem with a NAME token
        already minted in this conversation. Called under the lock."""
        # `_stem_of_word` strips ONE ending, so «Сазонов» gives «сазон» and
        # «Сазонова» gives «сазонов»; the man's and the woman's form of one
        # surname are related by prefix, not by equality.
        stems = {_stem_of_word(word.casefold()) for word in token.split()}
        rows = self._conn.execute(
            "SELECT token FROM tokens WHERE customer=? AND entity_type='NAME' AND minted_in=?",
            (self._customer, self._conversation),
        ).fetchall()
        return any(_stems_related(_stem_of_word(word.casefold()), stem)
                   for (other,) in rows for word in other.split() for stem in stems)

    def _shares_a_house_in_conversation(self, token: str) -> bool:
        """Whether a LOC token of this conversation carries the same house
        number as the candidate. Called under the lock."""
        house = morph_places.split_roles(token).get("house", "")
        if not house:
            return False
        rows = self._conn.execute(
            "SELECT token FROM tokens WHERE customer=? AND entity_type='LOC' AND minted_in=?",
            (self._customer, self._conversation),
        ).fetchall()
        return any(morph_places.split_roles(other).get("house", "") == house for (other,) in rows)

    def _shares_a_street_in_conversation(self, token: str) -> bool:
        """Whether a LOC token of this conversation already carries the
        candidate's street. Called under the lock."""
        stem = _street_stem(token)
        if not stem:
            return False
        rows = self._conn.execute(
            "SELECT token FROM tokens WHERE customer=? AND entity_type='LOC' AND minted_in=?",
            (self._customer, self._conversation),
        ).fetchall()
        return any(_street_stem(other) == stem for (other,) in rows)

    def _is_free_token(self, token: str, entity_type: str, original: str = "",
                       canonical: str = "") -> bool:
        """The four guards every candidate substitute passes, whether drawn at
        random or composed from parts already minted. Called under the lock."""
        if entity_type == "NAME" and original and _shares_a_word(token, original):
            return False
        # THE SAME RULE FOR A STREET. «Луговая» is in the fake pool because it
        # is a common street, and a common street is what the customer lives
        # on: drawn for «ул Луговая, д 10» it put the real street name into
        # the model's view labelled as ours (the register's neighbour record
        # did exactly that on the live run).
        if entity_type == "LOC" and original:
            fake_stem = _street_stem(token)
            if fake_stem and fake_stem == _street_stem(original):
                return False
        # The settlement of a city-bearing token is the ORIGINAL's own (see
        # `_settlement_of`), so no guard against a real town applies here any
        # more; the fake town is drawn only for a span that is a bare settlement,
        # which carries no comma and never reached the guard that stood here.
        if True:
            # THE ROW BEING MINTED IS NOT IN THE TABLE YET, so the lookup below
            # cannot see it and a substitute is free to come out equal to the
            # very value it replaces. Measured: «15.06.1963» minted as
            # «15.06.1963» — a date of birth «masked» into itself, indexed as a
            # token, and thereafter skipped by the re-masking guard for every
            # other person who shares it. The pools are large enough that this is
            # rare and small enough that it happens.
            if token == canonical or (original and token == original):
                return False
            # A SUBSTITUTE MAY NOT BE SOMEBODY'S REAL VALUE. `canonical` is the
            # key masking looks a value up by and `token` is the key
            # detokenization looks a string up by, so a string that is both
            # means two different people at once: the real bearer leaks (the
            # re-masking guard sees one of our tokens and lets it through), and
            # the model writing the substitute gets the OTHER person's data into
            # the tool — sometimes as a chimera, «Кирилл Бородин» restored as
            # «Ян Бородин», because the partial-name path resolves each word
            # against a different row.
            #
            # Measured on 2979 real people from NEREL: 3-7 substitutes per run
            # landed on a name the same customer already had, every one silent
            # and every one 200 OK.
            #
            # This closes the direction that is VISIBLE HERE. The other one — a
            # real person arriving later who bears a substitute minted earlier —
            # is not knowable at mint time and is answered by the conversation
            # scope on `is_minted_token` instead.
            #
            # THREE POINT QUERIES, NOT ONE `OR`. SQLite does not split an OR
            # across three different indexes: written as one predicate it
            # planned a range scan over every row the customer has — 1.27 ms on
            # a 20 000-row vault, growing with the vault, on a path that may run
            # 200 times. `UNION ALL` gives each branch its own covering index
            # and the whole check costs 2 microseconds.
            if self._conn.execute(
                "SELECT 1 FROM tokens WHERE customer=? AND token=? "
                "UNION ALL SELECT 1 FROM tokens WHERE customer=? AND canonical=? "
                "UNION ALL SELECT 1 FROM tokens WHERE customer=? AND canonical_fold=? "
                "LIMIT 1",
                (self._customer, token, self._customer, token,
                 self._customer, fold_key(token)),
            ).fetchone() is None:
                return True
        return False

    def for_conversation(self, conversation: str) -> "Vault":
        """A view of this vault scoped to ONE conversation.

        WHY A SCOPE EXISTS AT ALL. Linking a partial mention to a full one is
        only safe where the partial mention can be RESOLVED. «Ленина 14» exists
        in every Russian city, so in the space of one tenant it has a dozen
        candidates and the single-candidate rule refuses every time — the
        mechanism is not merely cautious there, it is dead. In one conversation
        there is normally one address in flight, so the rule fires and fires
        correctly. The scope is therefore not a way to reduce risk; it is the
        precondition that makes the rule mean anything, and both properties come
        from the same change.

        WHY A VIEW AND NOT A FIELD. The Vault is constructed per org and cached
        for the process, and several requests share it across threads. Writing
        the conversation onto the shared object would make one request's scope
        visible to another — the exact cross-customer link this scope exists to
        prevent. A shallow copy shares the connection and the lock (which is
        what must be shared) and owns the scope (which must not be).
        """
        view = copy.copy(self)
        view._conversation = conversation
        return view

    def with_pseudonym_scope(self, scope: str) -> "Vault":
        """A view whose question «is this string OUR substitute?» is asked at
        `scope`: `conversation` (the default) or `customer`.

        THE HOST'S MEMORY IS WHY THIS SETTING EXISTS. An agent with long-term
        memory recalls a fact from an earlier dialogue — and every framework in
        the field keys that store by USER, not by conversation (LangGraph Store,
        Mem0, Google ADK, Anthropic's memory tool; a `fork` and a per-agent
        handoff session do the same by other means). The recalled text carries
        the substitute the model was shown then. Judged at conversation scope
        that string is a stranger: it is masked a SECOND time, and the tool
        receives the first dialogue's fake — 200 OK, empty residual list, and
        nobody the wiser. Measured here, not argued.

        THE PRICE OF WIDENING IS A REAL PERSON. `is_minted_token` is what stops
        us re-masking our own substitute; widened to the customer it also stops
        us masking a REAL person who happens to bear a name minted for somebody
        else, and they reach the model in the clear for ever — 2-3 per run on
        2979 people from NEREL. So the default does not move: a host without
        memory must not pay for a problem it does not have, and 152-ФЗ counts
        the leak, not the broken tool call.

        A HOST THAT TURNS MEMORY ON DECLARES IT and trades that residual risk
        for consistency across dialogues; a host that can pass a customer-level
        conversation id instead pays nothing but the short-mention linking
        inside one dialogue.
        """
        if scope not in PSEUDONYM_SCOPES:
            raise ValueError(f"unknown pseudonym scope {scope!r}; expected one of {sorted(PSEUDONYM_SCOPES)}")
        view = copy.copy(self)
        view._pseudonym_scope = scope
        return view

    def with_own_values(self, values: tuple[str, ...]) -> "Vault":
        """A view that knows which strings belong to the HOST ITSELF.

        ДВА СЛУЧАЯ, И ОБА ЛОМАЮТ РАЗГОВОР, А НЕ ВОССТАНОВЛЕНИЕ.

        У АССИСТЕНТА ЕСТЬ ИМЯ. «Я Татьяна, голосовой ассистент» стоит в
        системном промпте, клиент здоровается — «здравствуйте, Татьяна», — и это
        имя маскируется: модель читает обращение к постороннему человеку и
        отвечает на него как на постороннего. Системный промпт на плече движка
        и так не маскируется (`skip_template`) ровно по этой причине — он
        шаблон агента, а не данные субъекта; реплика клиента, называющая то же
        имя, до сих пор такого признания не имела.

        У ЗАКАЗЧИКА ЕСТЬ АДРЕС. Промпт или справочник говорит «мы на Ленина
        14», клиент спрашивает «а вы на Ленина 14?» — вопрос маскируется,
        агент видит «Пушкина 10» и отвечает «нет, мы на Ленина 14». Разговор
        сломан целиком, и ни одна ось восстановления этого не видит: значение
        доехало бы верно, если бы до инструмента вообще дошло.

        ЭТО НЕ ПЕРСОНАЛЬНЫЕ ДАННЫЕ ПО ОПРЕДЕЛЕНИЮ. Субъект по 152-ФЗ ст. 3 п. 1
        — физическое лицо; ассистент им не является, а адрес компании
        идентифицирует юрлицо, которое Recital 14 и определение субъекта выводят
        из-под регламента. Тот же довод, по которому мы отказываемся маскировать
        голый город.

        ПУСТОЙ СПИСОК ПО УМОЛЧАНИЮ, И ЭТО ГЛАВНОЕ СВОЙСТВО: пока хост ничего не
        объявил, поведение движка не меняется НИ В ОДНОМ БАЙТЕ. Регрессия здесь
        невозможна по построению, а не по измерению.

        ЦЕНА НАЗВАНА: клиент, чьё упоминание сворачивается в ТОТ ЖЕ ключ, уйдёт
        к модели открытым. Ключ узкий — `name_key` для имени (именительный,
        строчными) и `address_key` для адреса, — поэтому «Татьяна Смирнова»
        сюда не попадает (это другой ключ), а «Татьяна» одним словом попадёт.
        Хост объявляет СВОИ значения, и цену этого объявления платит он же —
        ровно как с `pseudonym_scope`.
        """
        view = copy.copy(self)
        keys: set[str] = set()
        for value in values:
            text = value.strip()
            if not text:
                continue
            for signature in _OWN_SIGNATURES:
                try:
                    key = signature(text)
                except Exception:  # noqa: BLE001 — морфология не должна ронять запрос
                    continue
                if key:
                    keys.add(key)
        view._own_keys = frozenset(keys)
        return view

    def with_spent_signatures(self, signatures: frozenset[str]) -> "Vault":
        """Вид, который знает, какие подмены агент написал В ЭТОМ ВЫЗОВЕ
        ЦЕЛИКОМ — и поэтому не считает их же цифры ещё одним упоминанием.

        СТОЛКНОВЕНИЕ ВНУТРИ СВОЕГО ЖЕ РАЗГОВОРА ОБЛАСТЬЮ НЕ ЗАКРЫВАЕТСЯ И
        ЗАКРЫТО БЫТЬ НЕ МОЖЕТ (Б29). «Количество: 222» заказчика действительно
        лежит внутри цифр фейковой трубки ЭТОГО же диалога, и утверждение
        «ровно одна наша подмена носит эти цифры» истинно — замер дал 5 из 5
        молча переписанных количеств там, где разговор НАЗВАН. Но подмену агент
        уже написал целиком, в соседнем поле того же вызова, и она там уже
        восстановлена: подмену отдают один раз и один раз называют, поэтому
        второе число рядом с ней — это не она.

        ПО ЦИФРОВОЙ ПОДПИСИ, А НЕ ПО СТРОКЕ: агент переписывает телефон через 8
        и голыми цифрами, строка при этом другая, значение то же. Подпись — то,
        чем волт и так индексирует переформатированную подмену (`digits`),
        поэтому сравнение здесь не заводит второго понятия.

        ВИД, А НЕ ПОЛЕ, по той же причине, что и у `for_conversation`: волт один
        на орг и живёт в нескольких потоках, а написанное принадлежит одному
        вызову.

        ЦЕНА ОДНОСТОРОННЯЯ, И ОНА НАЗВАНА В ОСТАТКЕ, А НЕ ТОЛЬКО ЗДЕСЬ: схема,
        которая просит и телефон целиком, и его последние четыре цифры, получит
        в хвостовом поле фейковый хвост — но `digit_fragment_is_ours` о нём
        ДОЛОЖИТ, и шлюз заказчика увидит непустой остаток при 200. Здесь стояло
        обратное — вето гасило и сигнал, «потому что кусок принадлежит
        заказчику», — и отказ получался молчаливым: заказчик не узнавал о нём
        никогда. Порядок тяжести прямой: порча данных хуже молчаливой потери,
        молчаливая потеря хуже названной, названная хуже ложной тревоги. Вето
        покупает первое ценой третьего, а не второго.

        ПЛЕЧО У ВЕТО ОДНО — АРГУМЕНТ. Почему проза его не читает и почему иначе
        расходятся буфер и поток — `redact._argument_view`.
        """
        view = copy.copy(self)
        view._spent_signatures = signatures
        return view

    def with_written_digits(self, runs: tuple[str, ...]) -> "Vault":
        """Вид, который знает КАЖДОЕ ЧИСЛО, написанное агентом в этом вызове, —
        свидетельство, пришивающее кусок к целой подмене за пределами разговора.

        ОБЛАСТЬ СТОРОЖИТ КУСОК, НО ОТВЕЧАЕТ НЕ НА ВСЁ. Внутри разговора «ровно
        одна наша подмена носит эти цифры» что-то значит — подмен там единицы.
        По всему волту заказчика то же утверждение истинно почти для любых трёх
        цифр, и на место его собственного количества молча вставали цифры
        ЧУЖОГО НАСТОЯЩЕГО телефона (Б29). Сузить область до разговора и на этом
        остановиться нельзя: у обратного прокси ключ разговора ВСЕГДА выведен
        из транскрипта и никогда не равен тому, в котором подмена отчеканена, —
        паспорт, разложенный схемой на серию и номер, не возвращался бы вовсе,
        и тоже молча. Поэтому за пределами НАЗВАННОГО разговора отвечает не
        область, а ЯКОРЬ: разбили ли числа ЭТОГО ЖЕ вызова цифры подмены встык
        и целиком
        (`_tiling`). Серия плюс номер разбивают; голое «218» не разбивает
        ничего и остаётся числом заказчика.

        ВИД, А НЕ ПОЛЕ, по той же причине, что и у `for_conversation`: волт один
        на орг и живёт в нескольких потоках, а написанное принадлежит одному
        вызову.
        """
        view = copy.copy(self)
        view._written_digits = runs
        return view

    def whole_substitute_signatures(self, written: frozenset[str]) -> frozenset[str]:
        """Из строк, написанных агентом, — цифровые подписи тех, что являются
        нашими подменами ЦЕЛИКОМ.

        Спрашивается по точному токену и по подписи: обе колонки уже
        проиндексированы, и обе — то, чем `detokenize_many` узнаёт целую
        подмену. Ни одного нового понятия и ни одного лишнего чтения волта
        сверх одного пакетного запроса на вызов."""
        asked = sorted(text for text in written if text)
        if not asked:
            return frozenset()
        signatures = sorted({digits for digits in
                             ("".join(ch for ch in text if ch.isdigit()) for text in asked)
                             if len(digits) >= _WHOLE_SIGNATURE_MIN})
        # Ветки собираются по одной: `IN ()` — синтаксическая ошибка SQLite, а
        # не пустое множество, и вызов без единого длинного числа — обычное дело.
        clauses = [f"token IN ({','.join('?' * len(asked))})"]
        args: list[str] = list(asked)
        if signatures:
            clauses.append(f"digits IN ({','.join('?' * len(signatures))})")
            args.extend(signatures)
            clauses.append(f"digits10 IN ({','.join('?' * len(signatures))})")
            args.extend(signatures)
        with self._lock:
            rows = self._conn.execute(
                "SELECT digits FROM tokens WHERE customer=? AND digits IS NOT NULL "
                f"AND ({' OR '.join(clauses)})",
                (self._customer, *args),
            ).fetchall()
        return frozenset(row[0] for row in rows if row[0])

    def is_own_value(self, text: str) -> bool:
        """Строка, которую хост объявил СВОЕЙ: имя ассистента, адрес компании."""
        if not self._own_keys or not text.strip():
            return False
        for signature in _OWN_SIGNATURES:
            try:
                key = signature(text.strip())
            except Exception:  # noqa: BLE001
                continue
            if key and key in self._own_keys:
                return True
        return False

    def tokenize(self, value: str, entity_type: str) -> str:
        with stage("vault.tokenize"):
            return self._tokenize(value, entity_type)

    def tokenize_person(self, value: str, cases: tuple[str, ...]) -> str:
        """`tokenize` for a NAME whose sentence says which cases it may be in
        (`detect.NameSpan`); the key and the substitute's gender follow one
        reading of the phrase instead of two votes."""
        return self._tokenize(value, "NAME", cases)

    def _tokenize(self, value: str, entity_type: str, cases: tuple[str, ...] = ()) -> str:
        token = self._tokenize_unrecorded(value, entity_type, cases)
        if entity_type == "NAME" and self._conversation:
            self._record_use(token)
        return token

    def _record_use(self, token: str) -> None:
        """This conversation was shown this substitute — see `token_uses`."""
        with self._lock:
            self._expire_place_parts()
            self._conn.execute(
                "INSERT OR IGNORE INTO token_uses (customer, token, conversation, created) "
                "VALUES (?,?,?,?)",
                (self._customer, token, self._conversation, time.time()))
            self._conn.commit()

    def _tokenize_unrecorded(self, value: str, entity_type: str, cases: tuple[str, ...] = ()) -> str:
        canonical = (canonicalize_person(value, cases) if entity_type == "NAME" and cases
                     else canonicalize(entity_type, value))
        with self._lock:
            row = self._conn.execute(
                "SELECT token FROM tokens WHERE customer=? AND canonical=?",
                (self._customer, canonical),
            ).fetchone()
            if row is not None:
                return row[0]
            # A LINKED ADDRESS IS OWNED BY ITS CONVERSATION, so it is stored
            # under a key that carries one. «Ленина 14» resolved against the
            # full address of THIS dialogue must not be served to the next
            # customer who writes the same street — that is a courier sent to
            # whoever spoke first, and it is exactly what the conversation scope
            # exists to prevent. Written plainly, the row in `tokens` would have
            # leaked the link straight past that scope on the very next request.
            #
            # Full addresses keep the plain key: one place, one substitute, for
            # ever and across conversations. Only the derived short form is
            # scoped, because only it was a guess about which place was meant.
            scoped = f"{self._conversation}\x00{canonical}"
            if entity_type == "LOC" and self._conversation:
                row = self._conn.execute(
                    "SELECT token FROM tokens WHERE customer=? AND canonical=?",
                    (self._customer, scoped),
                ).fetchone()
                if row is not None:
                    return row[0]
            # The REAL person's gender decides the fake's, so the substitute
            # agrees with the sentence around it and the model leaves it alone.
            gender = (morph_names.read_person(value, cases)[0]
                      if entity_type == "NAME" else None)
            if entity_type == "NAME":
                # The FOLD first: it is one indexed point query and it catches
                # the two commonest ways one person is written twice — a
                # different capitalisation and е for ё.
                folded = self._conn.execute(
                    "SELECT token FROM tokens WHERE customer=? AND canonical_fold=?",
                    (self._customer, fold_key(canonical)),
                ).fetchone()
                if folded is not None:
                    return folded[0]
                reordered = self._same_person_reordered(canonical)
                if reordered is not None:
                    return reordered
            shape = morph_places.place_shape(value) if entity_type == "LOC" else {}
            extends: str | None = None
            token = None
            linked_place = None
            if entity_type == "NAME":
                linked = self._linked_token(canonical, value)
                if linked is not None:
                    token, extends = linked
                elif self._conversation:
                    grown = self._extends_known_person(canonical, value, gender)
                    if grown is not None:
                        token, extends = grown
                    else:
                        initials = self._initials_reuse(canonical, value)
                        if initials is not None:
                            token, extends = initials
            elif entity_type == "LOC":
                same = self._same_place_written_differently(canonical, value, shape)
                if same is not None:
                    # Not a guess, so the PLAIN canonical keeps it: one place,
                    # one substitute, and `linked_place` set so the second
                    # writing is not indexed as a second owner.
                    token, extends = same
                    linked_place = same
                else:
                    linked_place = self._linked_place(canonical, value, shape)
                if linked_place is not None and same is None:
                    (token, extends), canonical = linked_place, scoped
                elif token is None and self._conversation:
                    grown_place = self._extends_linked_place(canonical, value, shape)
                    if grown_place is not None:
                        token, extends = grown_place
            if token is None:
                head = (self._same_street_in_conversation(value, shape)
                        if entity_type == "LOC" else "")
                token = self._unique_token(entity_type, gender, value, canonical, head)
            if entity_type == "PHONE" and any(ch.isdigit() for ch in value):
                # THE SUBSTITUTE IS WRITTEN THE WAY THE CUSTOMER WROTE THE REAL
                # ONE. The vault minted «+79782727764» and the text showed
                # exactly that where the customer had typed «89896866953» or
                # «8-999-106-11-83» — a number in a machine's form inside a
                # human's sentence; in the correction family the gateway arm
                # then treated the contact as already on file and did not save
                # the card (six triples, 04.09). Rendered ONCE, at the mint, so
                # one person stays one string across the dialogue — the same
                # digits under whatever form the customer used first — and the
                # digit-signature index resolves every rewriting of it.
                token = _digits_in_customer_form(value, token)
            elif entity_type in _NUMERIC_TYPES and any(ch.isdigit() for ch in value):
                # EVERY OTHER IDENTIFIER, THE SAME WAY: the customer's
                # grouping, not the register's. See `_digits_laid_like`.
                token = _digits_laid_like(value, token)
            elif entity_type == "PLATE":
                # А ГОСНОМЕР ЗЕРКАЛИТСЯ ЦЕЛИКОМ, А НЕ ТОЛЬКО ЦИФРАМИ: у него
                # нотация — это ещё и РЕГИСТР, АЛФАВИТ, РАЗДЕЛИТЕЛИ и ДИКТОВКА.
                # ГОСТ-канон «А123ВС777» показывался там, где клиент написал
                # «у493са 23» или продиктовал «о сто пятнадцать у ка девяносто
                # девять»: 1 из 10 листьев у g03, 27 листьев IN/user в одной
                # группе g05. Нотация решается в `notation` — здесь только
                # вызов, потому что минт задаёт её ПЕРВЫМ и невозвратно
                # (SPIKE-А, механизм 1 и 6).
                token = notation.plate_laid_like(value, token)
            elif entity_type == "NAME":
                # СКРИПТ — ТАКАЯ ЖЕ ОСЬ, КАК РЕГИСТР. `Evgeniy Volnov` получал
                # кириллическую подмену, и модель вела себя иначе, чем без нас:
                # латинское имя — признак другого человека для агента, который
                # читает карточку (g15 office-002). Подмена наследует скрипт
                # источника, а минт индексирует скриптовое написание
                # (`token_parts` ниже), иначе латинская подмена молча перестала
                # бы разрешаться.
                token = notation.name_in_script(token, value)
            digits, digits10 = _digit_signatures(token, entity_type)
            # `value` (not `canonical`) — the surface form the user actually
            # typed, which is what the tool must receive. First writer wins: the
            # same person written two ways keeps the form seen first, so what the
            # tool gets is stable across turns instead of flipping with phrasing.
            try:
                self._conn.execute(
                    "INSERT INTO tokens "
                    "(customer, canonical, entity_type, token, digits, digits10, "
                    "original, first_seen, name_key, canonical_fold, minted_in, extends) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (self._customer, canonical, entity_type, token, digits, digits10,
                     value, time.time(),
                     name_key(token) if entity_type == "NAME"
                     else place_key(token) if entity_type == "LOC" else None,
                     fold_key(canonical) if entity_type == "NAME" else None,
                     self._conversation, extends),
                )
            except IntegrityError:
                # ANOTHER PROCESS GOT THERE FIRST, and that is not an error.
                #
                # SELECT-then-INSERT is a race across PROCESSES; the lock above
                # only serialises threads inside one. Four workers behind a single
                # SO_REUSEPORT port masking the same person at the same instant is
                # not a rare interleaving — it is the ordinary shape of a burst,
                # because a burst is usually about one customer. Both workers miss
                # the SELECT, both INSERT, and the loser used to receive
                # `UNIQUE constraint failed` and hand the caller a 500.
                #
                # The winner wrote exactly what this call would have written, so
                # its row IS the answer. Found by packaging gate P5, which sends
                # 64 requests carrying the SAME personal data through four
                # processes — the conditions this race needs.
                self._conn.rollback()
                return self._existing_token(canonical)
            # Parts are indexed ONLY for multi-word names, and in one statement.
            # A single-word canonical has nothing a later mention could be a part
            # OF, so a row for it is pure write volume — and write volume is not
            # free here: four worker processes share this file, and the extra
            # INSERTs per name were enough to bring back `database is locked` on
            # 2 of 64 requests under the burst gate. The busy timeout already
            # absorbs a lot (see sqlite_setup); the fix is to not generate the
            # contention rather than to wait longer for it.
            parts = [word.casefold() for word in canonical.split() if len(word) > 2]
            if entity_type == "NAME" and len(parts) > 1:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO name_parts (customer, part, canonical) "
                    "VALUES (?,?,?)",
                    [(self._customer, part, canonical) for part in set(parts)])
            # A FULL ADDRESS IS INDEXED SO A LATER SHORT MENTION CAN FIND IT.
            # Only one that names a city: without one there is nothing shorter
            # for a mention to be, and indexing it would make the short form its
            # own owner and block the real one.
            # A CITY-LESS MENTION WITH A HOUSE IS INDEXED TOO, marked as such:
            # the fuller form may arrive LATER — from the directory, from the
            # CRM record a tool returns — and must find this one and grow it,
            # not mint a second place. `has_city=0` keeps it from ever being an
            # OWNER for a later short mention, which is the trap the previous
            # rule guarded against. A projection (`linked_place`) is never
            # indexed: it is a view of a full address, not a place of its own.
            if (entity_type == "LOC" and self._conversation and linked_place is None
                    and (shape.get("has_city") or shape.get("has_house"))):
                part = morph_places.street_house_key(value)
                if part:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO place_parts "
                        "(customer, conversation, part, canonical, created, has_city) "
                        "VALUES (?,?,?,?,?,?)",
                        (self._customer, self._conversation, part, canonical,
                         time.time(), 1 if shape.get("has_city") else 0))
                    self._expire_place_parts()
            # ЧАСТИ ПОДМЕНЫ — для NAME по словам, для LOC по сигнатуре.
            #
            # ПОЧЕМУ АДРЕС ТОЖЕ. Схемы инструментов раскладывают его по полям —
            # `dispatch_car(street, house, entrance)` — и `unmask_arguments`
            # обходит листья JSON независимо, так что «улица Тополиная» и «49»
            # приходят на разрешение поодиночке. Ключ целой фразы несёт ВСЕ её
            # цифры и фрагменту не равен по построению: 50 из 54 неразрешённых
            # аргументов живого прогона — ровно это. Без индекса частей фрагмент
            # не только не разрешался, но и не попадал в `residual_tokens`, то
            # есть фейковый адрес уходил в CRM клиента с 200 и пустым журналом.
            #
            # Части нормализованы ЛЕММОЙ, а не casefold: модель склоняет адрес
            # («улицу Тополиную»), и сравнение написанного не нашло бы ничего.
            fake_parts: set[str] = set()
            if entity_type == "NAME":
                # И КАК НАПИСАНО, И В ИМЕНИТЕЛЬНОМ. Модель называет человека в
                # том падеже, которого требует фраза — «Телефон Олеси?», «Софию
                # не беспокоить», — а части лежали ровно как написаны, поэтому
                # «олеси» не находило «олеся» и агент называл клиенту
                # выдуманное имя как его собственное. Приведение к именительному
                # здесь безопасно: это сторона ПОДМЕНЫ, тот же индекс, что и
                # `name_key`; на стороне настоящего значения оно осталось бы
                # запрещённым.
                fake_parts = set()
                for word in token.split():
                    if len(word) <= 2 and len(token.split()) > 1 and not word[:1].isupper():
                        continue   # a particle inside a phrase, not «Ян»
                    fake_parts.add(word.casefold())
                    fake_parts.add(morph_names.to_nominative(word).casefold())
                    # THE DERIVED FORMS THE MODEL WRITES. A cardholder field, a
                    # `name_latin`, a summary «| Латиница | Tsvetkov Vsevolod |»
                    # — the model transliterates the substitute it read, and
                    # none of those strings is the token. ONE key per declared
                    # rendering of the word: the four standards' spellings were
                    # indexed here and the model wrote a fifth
                    # («Meshcheryakova»), which reached the tool unresolved.
                    # The lookup folds what the model wrote, so the index must
                    # hold the fold of EVERY rendering `UNITS` declares — not
                    # only the default one. It was one key, and the two are not
                    # the same set: «Михаил» indexed as `mIXaIl`, the model's
                    # declared «MIHAIL» folds to `mIhaIl`, the miss left the
                    # FAKE given name in the customer's cardholder field beside
                    # the real surname. `declared_keys` is that set, and no
                    # string-level fold can replace it (see its docstring).
                    if translit.is_cyrillic_word(word):
                        fake_parts |= translit.declared_keys(word)
                    else:
                        # И САМА ЛАТИНСКАЯ ПОДМЕНА. Подмена наследует скрипт
                        # источника (`notation.name_in_script`), и её слова —
                        # латинские, поэтому `declared_keys` над ними молчит, а
                        # `residual_of` спрашивает латинское слово ФОЛДОМ, а не
                        # написанием. Без этой строки латинская подмена
                        # индексировалась бы одним написанием и не находилась
                        # бы ни одним из своих объявленных чтений.
                        fake_parts.add(translit.fold(word))
                fake_shape = morph_names.name_shape(token)
                fake_words = token.split()
                if len(fake_shape) == len(fake_words):
                    given = next((w for w, k in zip(fake_words, fake_shape) if k == "name"), "")
                    patronymic = next((w for w, k in zip(fake_words, fake_shape) if k == "patr"), "")
                    if given and patronymic:
                        fake_parts.add(translit.squeezed_initials((given, patronymic)))
            elif entity_type in ("DOB", "DATE"):
                # THE CANONICAL DATE, so a substitute said in words is found by
                # the «1955-08-17» the agent writes for it: the exact-token pass
                # reads the ISO back into «17.08.1955» and asks `date_owner`.
                date_key = _date_canonical(token)
                fake_parts = {date_key} if date_key else set()
            elif entity_type == "LOC":
                stems, numbers = morph_places.signature_parts(token)
                fake_parts = set(stems) | set(numbers)
                # The settlement is REAL, so it is not a piece of the fake: a
                # bare «Самара» in a tool argument is the customer's word, not
                # a residual of ours, and must not be resolved or reported.
                city = morph_places.split_roles(token).get("city", "")
                if city:
                    fake_parts -= set(morph_places.signature_parts(city)[0])
            if fake_parts:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO token_parts (customer, part, token) "
                    "VALUES (?,?,?)",
                    [(self._customer, part, token) for part in fake_parts])
            self._conn.commit()
            return token

    def _existing_token(self, canonical: str) -> str:
        """The token whichever process won the insert race wrote."""
        row = self._conn.execute(
            "SELECT token FROM tokens WHERE customer=? AND canonical=?",
            (self._customer, canonical),
        ).fetchone()
        if row is None:
            # The constraint fired and yet no row followed. That is not a race,
            # it is an inconsistent store, and a masking gateway must fail closed
            # rather than invent a substitute nobody can resolve.
            raise RuntimeError(
                f"lost the insert race for {canonical!r} but no row followed")
        return row[0]

    def real_place_with_stem(self, stem: str) -> bool:
        """Whether some REAL address of this customer names a settlement with
        this stem — the check that keeps a customer's own town from being read
        as somebody's bare fake city. One indexed prefix query."""
        with self._lock:
            return self._real_place_with_stem_locked(stem)

    def _real_place_with_stem_locked(self, stem: str) -> bool:
        """The same question asked from INSIDE the mint, which already holds
        the lock — `threading.Lock` is not re-entrant, and taking it twice was
        a silent hang on every address that carried a city."""
        stem = stem.lower()
        if not stem:
            return False
        # PREFIX ONLY: `address_key` writes the city first, so the index on
        # (customer, canonical) serves this; a `'% stem%'` form scanned every
        # address the customer has, per candidate, up to 200 times a mint.
        # The canonical AND the written form: «на Валдае, улица Мира 4» keys
        # as «улица валдай мир 4» (a town pymorphy does not tag), so only the
        # surface still starts with the city. SQLite's LIKE folds ASCII only,
        # hence both spellings of the first letter.
        row = self._conn.execute(
            "SELECT 1 FROM tokens WHERE customer=? AND entity_type='LOC' "
            "AND (canonical LIKE ? OR original LIKE ? OR original LIKE ?) LIMIT 1",
            (self._customer, f"{stem}%", f"{stem}%", f"{stem[:1].upper()}{stem[1:]}%"),
        ).fetchone()
        return row is not None

    def _fragment_scopes(self, clause: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Области, в которых этот фрагмент имеет право искаться, ПО ПОРЯДКУ:
        сначала свой разговор, потом весь заказчик. `clause` уже выбран
        вызывающим: `_MINTED_HERE_JOINED` для запроса через JOIN с алиасом `k`,
        `_MINTED_HERE` для запроса по `tokens` напрямую; пустая пара условий —
        это «весь волт», и отвечает он только при единственном кандидате.

        ДВА РЕЖИМА, И ВТОРОЙ ПЛАТИТ ЕДИНСТВЕННЫМ КАНДИДАТОМ. Есть разговор —
        спрашиваем только его строки (плюс строки без `minted_in`: том,
        записанный до появления столбца, сравнивать не с чем). Нет разговора —
        спрашиваем весь волт, и ответ принимается, только если кандидат ровно
        один. Требование единственности не новое: каждый из поисков
        предъявляет его и внутри разговора, потому что и там фрагмент может
        принадлежать двум подменам сразу. Полный разбор — у `_MINTED_HERE_JOINED`
        выше.

        ЦИФРОВОЙ КУСОК ХОДИТ СЮДА ТОЛЬКО БЕЗ РАЗГОВОРА, И ЭТО ОСТАВШАЯСЯ ЦЕНА
        (Б29). Разговор НАЗВАН — ищем только его строки, а за их пределами
        отвечает ЯКОРЬ ВЫЗОВА, а не область: разбили ли числа того же вызова
        цифры подмены без остатка (`digit_fragment_owner`). Разговор НЕ назван —
        первой и единственной областью остаётся весь волт с правилом
        единственного кандидата, и это по-прежнему утверждение о НАШИХ строках,
        а не о том, чьё число написал агент: замер 23.09.2026 — 1–2 собственных
        количества заказчика из 300 молча уезжают краем чужой подмены (на
        0.3.17 их было 6–9). Убрать и эту область значит потерять одинокий
        кусок без разговора совсем — «серия 4509» отдельным полем у хоста,
        который не передаёт `conversation_id`: одна плитка не разбивает ничего,
        и якорь ответить не может. Размен не сделан, а НАЗВАН: потеря была бы
        видимой (`digit_fragment_is_ours` области не спрашивает), но это
        отдельное решение и отдельный замер.

        ОБЪЯВЛЕННАЯ ПАМЯТЬ АГЕНТА — ЭТО ВТОРОЙ ШАГ, А НЕ ДРУГОЙ ПЕРВЫЙ.
        `with_pseudonym_scope("customer")` говорит, что хост носит подмены между
        диалогами, и до этих поисков объявление не доходило вовсе: фрагмент
        по-прежнему искался только в своём разговоре, то есть настройка держала
        целую подмену и роняла её часть. Наивное расширение — «объявили память,
        значит спрашиваем весь волт» — ломает того же хоста иначе: его
        СОБСТВЕННЫЙ адрес перестал бы разрешаться, как только другой диалог
        упомянул ту же улицу, потому что кандидатов стало двое. Поэтому шага
        два: своя строка отвечает первой и ни с кем не соревнуется, а весь
        заказчик спрашивается, только если дома ответа не нашлось, — и там
        действует то же правило единственного кандидата, что и у плеча без
        названного разговора."""
        if not self._conversation:
            return (("", ()),)
        if self._pseudonym_scope == "customer":
            return ((clause, (self._conversation,)), ("", ()))
        return ((clause, (self._conversation,)),)

    def fragment_scope_is_a_dialogue(self) -> bool:
        """Спрашивает ли поиск куска строки ОДНОГО ДИАЛОГА, а не весь волт.

        Читается из того же поля, из которого `_fragment_scopes` строит первую
        область, а не повторяет её условие другими словами: два отдельно
        написанных условия однажды разойдутся, и разойдутся именно здесь.

        ЗАЧЕМ ЭТО СПРАШИВАЮТ. Утверждение «ровно одна наша подмена носит это
        число» несёт разный вес в двух областях. В строках одного диалога
        адресных подмен единицы, и одинокое «дом 36» своему диалогу отвечает.
        По всему волту заказчика «носит ли какая-нибудь наша подмена дом 7»
        отвечает «да» почти всегда, и на место складского дома заказчика молча
        вставал дом ЧУЖОГО НАСТОЯЩЕГО адреса (Б29). Поэтому за пределами
        диалога адресные листья спрашиваются ПАРАМИ — см.
        `redact._address_owners`."""
        return bool(self._conversation)

    def _place_key_owners(self, name_key: str) -> tuple[set[str], bool]:
        """Адресные подмены заказчика, которые носят ВСЕ основы этого ключа, и
        было ли чтение обрезано потолком.

        ВОПРОС ЗАДАН ПО ОСНОВАМ, А НЕ ПО КЛЮЧУ, и это не мелочь: вырожденный
        ключ «каштановый|» принадлежит голой улице, а полный адрес того же
        названия ключуется «каштановый|60186» и по ключу не нашёлся бы — притом
        что слово «Каштановая» в поле `street` одинаково принадлежит обоим. Счёт
        по ключу назвал бы такого заказчика однозначным и отдал бы улицу первого
        диалога агенту второго, то есть ровно то раскрытие, ради запрета
        которого правило и написано. Основы лежат в `token_parts` — тот же
        индекс, которым отвечает `place_owner_by_street`, и тот же ответ: по
        одному точечному запросу на основу, независимо от размера волта.

        ОСНОВА БЕЗ ВЛАДЕЛЬЦЕВ ПРОПУСКАЕТСЯ, а не обнуляет ответ: город в подмене
        НАСТОЯЩИЙ и поэтому в `token_parts` не индексируется (см. чеканку), так
        что у ключа «каштановый|самара|» основа «самара» не найдёт ничего. Она и
        не должна: наше в этой строке — название улицы, и спрашивать надо о нём.

        ПОТОЛОК ЕСТЬ, И ОН НАЗЫВАЕТ СЕБЯ. Вызывающий спрашивает ровно одно:
        кандидат ОДИН или их несколько. У заказчика, где одну основу носят сотни
        подмен, ответ известен на пятьдесят первой, а полная выборка стоила бы
        размера волта на каждом вызове. Но обрезанное чтение — это «не знаю», а
        не «столько и есть»: `token_parts` держит и части ИМЁН, поэтому первые
        полсотни строк основы «ленин» могут оказаться людьми, а единственная
        улица — за краем. Поэтому потолок возвращается вторым значением, и
        вызывающий поворачивает от него в безопасную сторону — единственного
        кандидата нет, остаток виден.

        ДВА ЗАПРОСА, А НЕ ОДИН JOIN, И ЭТО РАЗНИЦА В ШЕСТЬСОТ РАЗ. У совмещённого
        запроса (как у `place_owner`) SQLite выбирает ведущей таблицей `tokens` и
        идёт по `idx_tokens_namekey (customer=?)`, то есть перебирает ВСЕ строки
        заказчика: 55 мс на 60 000 строк за одну основу. Разделённый запрос
        читает `token_parts` покрывающим индексом (customer, part) и добирает тип
        точечно по (customer, token) — 0.09 мс. Этот вопрос задаётся на каждый
        кандидат ответа, поэтому план здесь важнее краткости.
        """
        return self._loc_parts_owners([part for part in name_key.split("|") if part])

    def _loc_parts_owners(self, stems: list[str]) -> tuple[set[str], bool]:
        """Те же два запроса по списку частей, каким его даёт `signature_parts`
        — см. `_place_key_owners`, откуда взяты и план, и потолок."""
        if not stems:
            return set(), False
        truncated = False
        with self._lock:
            owners: set[str] | None = None
            for stem in stems:
                named = [row[0] for row in self._conn.execute(
                    "SELECT token FROM token_parts WHERE customer=? AND part=? LIMIT ?",
                    (self._customer, stem, _PLACE_OWNER_CAP + 1),
                ).fetchall()]
                truncated = truncated or len(named) > _PLACE_OWNER_CAP
                if not named:
                    continue
                found = {row[0] for row in self._conn.execute(
                    "SELECT token FROM tokens WHERE customer=? AND entity_type='LOC' "
                    f"AND token IN ({','.join('?' * len(named))})",
                    (self._customer, *named),
                ).fetchall()}
                if not found:
                    continue
                owners = found if owners is None else (owners & found)
                if not owners:
                    return set(), truncated
        return (owners or set()), truncated

    def _sole_place_owner(self, name_key: str) -> bool:
        """Ровно одна адресная подмена этого заказчика носит это название —
        условие, на котором плечо без названного разговора получает ответ.

        Несколько строк, которые НА САМОМ ДЕЛЕ одно место (короткое упоминание и
        выросший из него полный адрес), — это один кандидат; цепочку `extends`
        строит только этот код и только внутри разговора."""
        owners, truncated = self._place_key_owners(name_key)
        if truncated or not owners:
            return False
        if len(owners) == 1:
            return True
        if len(owners) > _ONE_IDENTITY_CAP:
            return False
        with self._lock:
            return self._one_identity(owners) is not None

    def place_owner(self, candidate: str, role: str) -> str | None:
        """Адресная подмена, ЧАСТЬЮ которой является этот фрагмент.

        РОЛЬ — ЭТО ЧАСТЬ ВОПРОСА (Б29). `role` — та роль, в которую кусок
        положил АГЕНТ: имя поля схемы (`role_of_field`) или подсказка в прозе
        («дом 41», «кв. 7»). Голое число признаётся нашим, только если подмена
        носит его ИМЕННО В ЭТОЙ РОЛИ: иначе «ровно одна наша подмена носит это
        число» — утверждение о НАШИХ строках, а не о том, чьё число написал
        агент, и складской дом заказчика молча уезжал в CRM номером ЧУЖОГО
        настоящего дома. Название улицы о себе говорит само (оно не бывает
        квартирой), поэтому фильтр стоит только на числах. Пустая роль значит
        «спрашивающий роли не знает» — так спрашивает прозаическое окно о
        целой адресной фразе, у которой роль не одна.

        Тот же вопрос, что `residual_of` задаёт про имя, и то же единственное
        правило, которое делает ответ безопасным: все части фрагмента должны
        сойтись на ОДНОЙ подмене. Улица без дома у клиента с двумя адресами на
        ней даёт двух владельцев, и тогда ответа нет — вернуть любого из них
        значило бы отправить курьера к тому, кто просто говорил первым.

        Части берутся сигнатурой, а не написанием: поле схемы приходит
        склонённым («улицу Тополиную») и сокращённым («ул. Тополиная»), и
        сравнение строк не нашло бы ничего.
        """
        stems, numbers = morph_places.signature_parts(candidate)
        # ГОРОД ЗАПИСИ НЕ ЯВЛЯЕТСЯ ЧАСТЬЮ ПОДМЕНЫ, И СПРАШИВАТЬ ЕГО НЕЛЬЗЯ
        # (Б-4). Поселение в подмене НАСТОЯЩЕЕ by design — оно не индексируется
        # в `token_parts` (см. чеканку), — поэтому написанная фраза с городом не
        # сходилась ни на одной подмене ЦЕЛИКОМ: «сортавала, улица липовая 22»
        # резолвилось окном покороче — улицей, — а дом оставался подменой, и
        # инструмент получал СМЕСЬ настоящей улицы с фальшивым домом при 200 и
        # пустом `residual_tokens` (g08/single-005: «улица настоящая, дом 22
        # остался подстановкой»).
        #
        # ВОПРОС ЗАДАЁТСЯ БЕЗ ГОРОДА, НО ГОРОД ПРИ ЭТОМ ПРОВЕРЯЕТСЯ ОТДЕЛЬНО.
        # Просто выкинуть его нельзя: «Самара, мятная 10» — это слова МОДЕЛИ
        # поверх голой записи клиента («луговая 10»), и без сверки города
        # целая фраза разрешалась бы, а `in_form_of` снесла бы агентское
        # «Самара,» как часть, которой у записи нет (test_product: клиент
        # ничего не дописывает и не чинит). Поэтому город обязан сойтись с
        # городом подмены, когда подмена его называет; подмена БЕЗ города
        # владельцем фразы с городом не становится — её разберёт окно покороче,
        # а город агента останется как написан.
        city = morph_places.split_roles(candidate).get("city", "")
        city_stems = set(morph_places.signature_parts(city)[0]) if city else set()
        if city_stems:
            stems = tuple(stem for stem in stems if stem not in city_stems)
        parts = [*stems, *numbers]
        if not parts:
            return None
        # ОБЛАСТЬ РАЗГОВОРА ОБЯЗАТЕЛЬНА ЗДЕСЬ, а не желательна. Целая подмена
        # уникальна, и разрешать её по всему клиенту безопасно: назвать её мог
        # только тот, кому мы её отдали. ФРАГМЕНТ не уникален — «Полевая 35»
        # выглядит одинаково у всех, — и без области диалог B получал адрес,
        # отчеканенный в диалоге A. Это ровно то раскрытие, ради запрета
        # которого область и заведена. Плечо, разговора не назвавшее, спрашивает
        # весь волт и платит за это единственным кандидатом ниже; хост, который
        # объявил память агента, спрашивает сначала свой разговор, потом весь
        # волт — по тому же правилу (`_fragment_scopes`).
        number_role = role if role and not stems else ""
        for scope, scope_args in self._fragment_scopes(_MINTED_HERE_JOINED):
            found = self._place_owner_in(parts, scope, scope_args, number_role)
            if found is not None:
                if city_stems and not _settlement_of(found):
                    # ГОРОД НАЗВАН, А ПОДМЕНА ГОРОДА НЕ НОСИТ. Значит, город в
                    # фразе — слова агента поверх ГОЛОЙ записи клиента
                    # («Самара, мятная 10» для записи «луговая 10»), и объявить
                    # её подменой ЦЕЛИКОМ нельзя: `in_form_of` снёс бы
                    # агентское «Самара,» как часть, которой у записи нет
                    # (test_product). Окно покороче разрешится само и оставит
                    # город как написан. Когда подмена город НЕСЁТ, целая фраза
                    # разрешается: город в ней либо тот же, либо подменён
                    # агентом — из записи вернётся настоящий.
                    return None
                return found
        return None

    def _place_fragment_owners(self, parts: list[str], scope: str,
                               scope_args: tuple[str, ...]) -> set[str]:
        """Адресные подмены, которые носят ВСЕ эти части, в одной области."""
        with self._lock:
            owners: list[set[str]] = []
            for part in parts:
                rows = self._conn.execute(
                    "SELECT t.token FROM token_parts AS t "
                    "JOIN tokens AS k ON k.customer=t.customer AND k.token=t.token "
                    "WHERE t.customer=? AND t.part=? AND k.entity_type='LOC'"
                    + scope,
                    (self._customer, part, *scope_args),
                ).fetchall()
                if not rows:
                    return set()
                owners.append({row[0] for row in rows})
        return set.intersection(*owners)

    def _place_owner_in(self, parts: list[str], scope: str,
                        scope_args: tuple[str, ...], number_role: str) -> str | None:
        """`place_owner` в ОДНОЙ области — см. там. `number_role` отсеивает
        подмены, которые носят это число В ДРУГОЙ РОЛИ, и отсеивает ДО правила
        единственного владельца: отфильтруй он после, подмена с квартирой 41
        отобрала бы ответ у подмены с домом 41, и дом не восстановился бы."""
        common = self._place_fragment_owners(parts, scope, scope_args)
        if number_role:
            # ТОТ ЖЕ ВОПРОС, ЧТО ЗАДАЁТ СИГНАЛ, И ТОТ ЖЕ КОД. Написанный здесь
            # второй раз, он однажды разошёлся бы с сигналом — и наружу это
            # выглядело бы как «остаток назвал наш дом, а восстановление его не
            # тронуло», то есть ложная тревога на пустом месте.
            common = {token for token in common
                      if _wears_parts_in_role(token, (), tuple(parts), number_role)}
        if len(common) == 1:
            return next(iter(common))
        if not common:
            return None
        # Two owners that are ONE place — the short mention and the full one
        # grown from it — answer with the fullest; two real places refuse.
        with self._lock:
            return self._one_identity(common)

    def place_owner_of_whole(self, written: tuple[tuple[str, str], ...]) -> str | None:
        """Адресная подмена, КАЖДУЮ роль которой назвал ЭТОТ вызов — и потому
        не фрагмент. `written` — пары (роль, как написал агент).

        РАЗЛОЖЕННОЕ ПО ПОЛЯМ ЦЕЛОЕ — ЭТО ЦЕЛОЕ, А НЕ КУСКИ (Б29, второй
        дефект). Схема просит `street`, `house` и `flat` порознь, агент
        раскладывает по ним ОДНУ нашу подмену, и каждый лист поодиночке
        становится куском, у которого якорь один — разговор. Обратный прокси
        разговор ВЫВОДИТ из транскрипта, поля для него у чат-API нет, и
        выведенный ключ не равен тому, в котором подмена отчеканена: целый
        адрес пропадал МОЛЧА, 15 из 15 на любой наполненности. Вместе же эти
        листы называют подмену ЦЕЛИКОМ — занята каждая её роль и ни одной
        лишней, — а целая подмена уникальна по построению и всегда разрешалась
        по всему заказчику обычным путём. Область разговора сторожит КУСОК
        (Б23), и здесь её нет не потому, что её ослабили, а потому что куска
        нет.

        РОВНО РАВЕНСТВО НАБОРОВ РОЛЕЙ, А НЕ ПОКРЫТИЕ. «улица + дом» у подмены,
        которая несёт ещё и квартиру, — это по-прежнему кусок: квартиру агент
        не написал, и назвать эту подмену целой нечем. Требование
        единственного кандидата остаётся: две подмены с одинаковыми ролями —
        отказ, а не выбор.
        """
        by_role = {role: morph_places.signature_parts(value) for role, value in written}
        parts = [part for stems, numbers in by_role.values() for part in (*stems, *numbers)]
        if len(by_role) < 2 or not parts:
            return None
        # ПОД-РОЛИ УЛИЦЫ — ПОЛОВИНЫ ОДНОЙ РОЛИ, А НЕ САМОСТОЯТЕЛЬНЫЕ ЧАСТИ: у
        # `street_type` нет ни основы, ни числа, и в сравнении наборов ролей он
        # не участвует (иначе схема со `street` + `street_type` не называла бы
        # подмену целой никогда). Убираются с ОБЕИХ сторон — симметрично.
        named_roles = {role for role in by_role if role not in morph_places._STREET_SUB_ROLES}
        owners = self._place_fragment_owners(parts, "", ())
        whole = {token for token in owners
                 if {role for role in morph_places.split_roles(token)
                     if role not in morph_places._STREET_SUB_ROLES} == named_roles
                 and all(_wears_parts_in_role(token, stems, numbers, role)
                         for role, (stems, numbers) in by_role.items())}
        return next(iter(whole)) if len(whole) == 1 else None

    def place_owner_by_street(self, candidate: str) -> str | None:
        """TWO PLACES ON ONE STREET, ASKED ABOUT THE STREET ALONE. A corrected
        address is two tokens on one fake street by construction, and a
        `street` field holding that street has two owners whose answer is THE
        SAME street. The latest mention wins — the correction is the later one
        and its spelling is what the customer settled on.

        A SEPARATE QUESTION FROM `place_owner`, AND THE CALLER ASKS IT LAST.
        Folded into `place_owner` it broke the address join: the join asks
        every leaf for its owner and demands ONE, so a street leaf answering
        with the latest row while the house leaf answered with the row that
        carries that house made two owners of one address — and the fake
        house went to the courier (r2 run, compare-002/012). The join asks
        this only when no leaf with a number found an owner.
        """
        stems, numbers = morph_places.signature_parts(candidate)
        if numbers or not stems:
            return None
        # ГОРОД ЗДЕСЬ ТАК ЖЕ НЕ ЧАСТЬ ПОДМЕНЫ — см. `place_owner`. Поле `street`,
        # в котором агент оставил город («Сортавала, улица Ольховая»), иначе не
        # находило владельца вовсе, и остаток не назывался.
        city = morph_places.split_roles(candidate).get("city", "")
        city_stems: set[str] = set()
        if city:
            city_stems = set(morph_places.signature_parts(city)[0])
            stems = [stem for stem in stems if stem not in city_stems]
            if not stems:
                return None
        for scope, scope_args in self._fragment_scopes(_MINTED_HERE_JOINED):
            found = self._street_owner_in(stems, scope, scope_args)
            if found is not None:
                if city_stems and not _settlement_of(found):
                    return None
                return found
        return None

    def _street_owner_in(self, stems: list[str], scope: str,
                         scope_args: tuple[str, ...]) -> str | None:
        """`place_owner_by_street` в ОДНОЙ области — см. там."""
        with self._lock:
            owners: list[set[str]] = []
            for part in stems:
                rows = self._conn.execute(
                    "SELECT t.token FROM token_parts AS t "
                    "JOIN tokens AS k ON k.customer=t.customer AND k.token=t.token "
                    "WHERE t.customer=? AND t.part=? AND k.entity_type='LOC'"
                    + scope,
                    (self._customer, part, *scope_args),
                ).fetchall()
                if not rows:
                    return None
                owners.append({row[0] for row in rows})
            common = set.intersection(*owners)
            if len(common) < 2:
                return next(iter(common)) if common else None
            # «ПОЗДНЕЕ УПОМИНАНИЕ ПОБЕЖДАЕТ» — ПРАВИЛО ОДНОГО РАЗГОВОРА. Оно
            # разбирает исправленный адрес: две строки на одной фейковой улице,
            # и поздняя — то написание, на котором заказчик остановился. Между
            # РАЗНЫМИ диалогами «позже» не значит ничего, кроме «кто-то другой
            # говорил последним», поэтому проход ПО ВСЕМУ ЗАКАЗЧИКУ видит здесь
            # двух кандидатов и отказывает — и у плеча без названного разговора,
            # и у второго шага объявленной памяти агента. Признак прохода —
            # его собственные параметры области, а не поле вида: при
            # `pseudonym_scope=customer` разговор назван, а второй проход всё
            # равно стоит вне его.
            if not scope_args:
                return None
            rows = self._conn.execute(
                "SELECT rowid, token, canonical FROM tokens WHERE customer=? AND entity_type='LOC' "
                f"AND token IN ({','.join('?' * len(common))}) ORDER BY rowid",
                (self._customer, *sorted(common)),
            ).fetchall()
            street_stems = [_street_stem(morph_places.street_house_key(canonical)) for _, _, canonical in rows]
            if len(rows) >= 2 and all(_street_stems_match(street_stems[0], other) for other in street_stems[1:]):
                return rows[-1][1]
            return None

    def date_owner(self, reading: str, for_tool: bool = False) -> str | None:
        """The real value behind a DATE/DOB substitute whose canonical «dd.mm.yyyy»
        is `reading` — the way a substitute SAID IN WORDS is found once the
        agent has rewritten it as ISO. Conversation-scoped like every fragment
        lookup: two dialogues may well hold substitutes on one date."""
        if not reading:
            return None
        for scope, scope_args in self._fragment_scopes(_MINTED_HERE_JOINED):
            values = self._date_values_in(reading, for_tool, scope, scope_args)
            if len(values) == 1:
                return next(iter(values))
        return None

    def _date_values_in(self, reading: str, for_tool: bool, scope: str,
                        scope_args: tuple[str, ...]) -> set[str]:
        """Настоящие даты, стоящие за этим прочтением, в ОДНОЙ области."""
        with self._lock:
            # DISTINCT, А НЕ ПРОСТО LIMIT: три одинаковых строки исчерпывали
            # предел и прятали четвёртую, с ДРУГОЙ датой, — то есть «кандидат
            # один» говорилось про усечённый список. Отдельные значения
            # различаются в трёх первых строках или их заведомо больше одного.
            rows = self._conn.execute(
                "SELECT DISTINCT k.entity_type, k.canonical, k.original FROM token_parts AS t "
                "JOIN tokens AS k ON k.customer=t.customer AND k.token=t.token "
                "WHERE t.customer=? AND t.part=? AND k.entity_type IN ('DOB','DATE')"
                + scope + " LIMIT 3",
                (self._customer, reading, *scope_args),
            ).fetchall()
        return {_pick_value(row[0], row[1], row[2], for_tool) for row in rows}

    def digit_fragment_owner(self, fragment: str, entity_type: str | None = None,
                             position: str | None = None) -> tuple[str, str] | None:
        """Настоящие цифры на МЕСТЕ этого куска чужой подмены, и её тип.

        ПОЛЕ СХЕМЫ БЫВАЕТ МЕНЬШЕ ЗНАЧЕНИЯ. Российская форма просит серию и номер
        паспорта ОТДЕЛЬНО, оператор переспрашивает последние четыре цифры
        телефона, СНИЛС диктуют группами. Агент кладёт в такое поле КУСОК
        подмены, целая сигнатура его не находит — и кусок уходил в инструмент
        как есть, то есть ФЕЙКОМ, с кодом 200 и пустым списком остатков. Ни
        одного способа заметить это снаружи не было.

        ОТВЕЧАЕТ СМЕЩЕНИЕ, А НЕ НОМЕР ГРУППЫ. «26 35 534625» и «4509 123456»
        разбиты на группы по-разному, но цифры стоят на одних местах: серия —
        первые четыре, номер — следующие шесть. Кусок ищется в цифрах подмены,
        и на том же смещении берутся цифры настоящего значения.

        ОБЛАСТЬ РАЗГОВОРА И ЕДИНСТВЕННЫЙ КАНДИДАТ — как у `place_owner`, и по
        той же причине: «35» встречается в цифрах половины подмен клиента.
        Несколько кандидатов означают отказ, а не выбор.

        ЗА ПРЕДЕЛАМИ НАЗВАННОГО РАЗГОВОРА ОТВЕЧАЕТ ЯКОРЬ, А НЕ ОБЛАСТЬ (Б29).
        Раньше чужой разговор — и второй шаг объявленной памяти агента —
        спрашивал ВЕСЬ волт с правилом единственного кандидата, а это
        утверждение о НАШИХ строках, не о том, чьё число написал агент: у
        заказчика с полусотней диалогов его собственное «количество: 106» лежит
        внутри цифр ровно одной фейковой трубки почти всегда, и на его место
        МОЛЧА вставали три цифры ЧУЖОГО НАСТОЯЩЕГО телефона. Просто убрать эту
        область нельзя: у обратного прокси разговор ВСЕГДА выведен из
        транскрипта, и паспорт двумя полями перестал бы возвращаться совсем.
        Поэтому она заменена вопросом, у которого есть ответ: разбили ли числа
        ЭТОГО ЖЕ вызова цифры подмены встык и целиком (`_digit_fragments_tiled`).

        ПЛЕЧО БЕЗ РАЗГОВОРА ВОВСЕ ЭТИМ НЕ ЗАКРЫТО, и разбор оставшейся цены — у
        `_fragment_scopes`: там весь волт остаётся ПЕРВОЙ областью, потому что
        одинокий кусок без разговора якорю не по зубам.

        КРАЙ ОБЯЗАТЕЛЕН, ПОКА О ВЫЗОВЕ НИЧЕГО НЕ ИЗВЕСТНО. `position` называет
        край, который назвала подсказка; `None` значит «подсказки не было», а НЕ
        «где угодно внутри»: кусок из середины цифр не стоит ни в одной роли,
        которую подмена несла на входе (`_stands_in_named_role`). Единственное
        исключение — и оно не послабление: когда числа ЭТОГО ЖЕ вызова разбили
        подмену встык и целиком, роль каждой плитки названа самим разбиением, и
        середина возвращается тоже (`_tiling`).
        """
        digits = "".join(ch for ch in fragment if ch.isdigit())
        if len(digits) < 2:
            return None
        for scope, scope_args in self._fragment_scopes(_MINTED_HERE):
            here = self._sole_fragment(self._digit_fragments_in(
                digits, entity_type, position, scope, scope_args))
            if here is not None:
                return here
        return self._sole_fragment(self._digit_fragments_tiled(digits, entity_type, position))

    def _sole_fragment(self, found: list[tuple[str, str, bool]]) -> tuple[str, str] | None:
        """Единственный ответ этих находок, если он единственный и если он не
        ветирован — ОДНО правило на обе политики поиска (`_digit_fragments_in` и
        `_digit_fragments_tiled`), потому что расходиться им нечем."""
        unique = {(value, kind) for value, kind, _ in found}
        if len(unique) != 1:
            return None
        answer = next(iter(unique))
        if all(spent for value, kind, spent in found if (value, kind) == answer):
            # ПОДМЕНУ ОТДАЮТ ОДИН РАЗ, И ОДИН РАЗ ЕЁ НАЗЫВАЮТ (Б29). Единственный
            # владелец этих цифр написан агентом целиком в ЭТОМ ЖЕ вызове и там
            # же восстановлен; число рядом с ним — не второе упоминание той же
            # подмены, а собственное число заказчика. Отказ, а не выбор: отказ
            # назовёт `surviving_substitutes`, а переписанное количество не
            # назвал бы никто. См. `with_spent_signatures`.
            return None
        return answer

    def _digit_rows(self, digits: str, entity_type: str | None, scope: str,
                    scope_args: tuple[str, ...]) -> list[tuple[str, str, str]]:
        """Строки волта, в цифрах которых стоит этот кусок: (цифры подмены,
        цифры настоящего значения, тип). ОДИН читатель на обе политики ниже —
        область и якорь отличаются тем, что они ДЕЛАЮТ со строкой, а не тем,
        какие строки видят."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT digits, entity_type, canonical, original "
                "FROM tokens WHERE customer=? AND digits IS NOT NULL "
                "AND length(digits) > ? AND instr(digits, ?) > 0"
                + scope,
                (self._customer, len(digits), digits, *scope_args),
            ).fetchall()
        read: list[tuple[str, str, str]] = []
        for token_digits, row_type, canonical, original in rows:
            if entity_type is not None and row_type != entity_type:
                continue
            value = _pick_value(row_type, canonical or "", original or "", True)
            real = "".join(ch for ch in value if ch.isdigit())
            if len(real) != len(token_digits):
                # Разной длины — смещение не переносится, и угадывать нельзя.
                continue
            read.append((token_digits, real, row_type))
        return read

    def _digit_fragments_in(self, digits: str, entity_type: str | None,
                            position: str | None, scope: str,
                            scope_args: tuple[str, ...]) -> list[tuple[str, str, bool]]:
        """Настоящие цифры на месте этого куска, в ОДНОЙ области, и была ли
        подмена-владелец уже написана в этом вызове целиком — см.
        `digit_fragment_owner`.

        СПИСКОМ, А НЕ МНОЖЕСТВОМ: один и тот же ответ может прийти и от
        ветированной подмены, и от невиновной, и слить их в одну пару значило
        бы решать судьбу куска по тому, какая строка волта прочиталась первой.

        THE CUE NARROWS THE QUESTION. «контрольное число 77» is the END of a
        СНИЛС, «серия 4509» the START of a passport, «последние четыре цифры
        телефона» the end of a phone — and a two-digit fragment read against
        every substitute's digits finds three owners and refuses, while read
        against one type at one position it has exactly one."""
        return [(real[start:start + len(digits)], row_type,
                 token_digits in self._spent_signatures)
                for token_digits, real, row_type in self._digit_rows(
                    digits, entity_type, scope, scope_args)
                for start in _placements(token_digits, digits, position)]

    def _digit_fragments_tiled(self, digits: str, entity_type: str | None,
                               position: str | None) -> list[tuple[str, str, bool]]:
        """Настоящие цифры на месте этого куска — по ВСЕМУ заказчику, но только
        у подмен, которые числа ЭТОГО ЖЕ вызова разбивают без остатка.

        ЯКОРЬ ВМЕСТО ОБЛАСТИ (Б29). Серия «4512» и номер «123456» в соседних
        полях одного вызова укладываются в цифры паспортной подмены встык и
        целиком — такое разбиение не бывает случайным и называет владельца само,
        без разговора: именно поэтому обратный прокси, у которого ключ разговора
        всегда выведен из транскрипта, здесь наконец отвечает. Голое
        «количество: 218» не укладывается ни во что и остаётся числом
        заказчика. Разбор правила — `_tiling` и `with_written_digits`.

        КРАЯ ЗДЕСЬ НЕ ТРЕБУЕТСЯ, И ЭТО НЕ ПОСЛАБЛЕНИЕ. Край — то единственное
        имя, которое есть у куска, когда о вызове не известно ничего; разбиение
        знает о вызове больше: оно доказывает, что схема разложила по своим
        полям ОДНО значение целиком. Требовать вдобавок края значило бы молча
        терять середину, у которой имя есть, — код оператора между страной и
        номером, внутренние группы СНИЛС и карты. Поэтому кусок принимается
        ровно тогда, когда он САМ является плиткой (`_tiling`), а не когда он
        просто лежит внутри разбитой подмены: «серия + номер + количество»
        разбивают паспорт серией и номером, и количество остаётся количеством."""
        return [(real[start:start + len(digits)], row_type,
                 token_digits in self._spent_signatures)
                for token_digits, real, row_type in self._digit_rows(
                    digits, entity_type, "", ())
                for start in sorted(at for at, run in _tiling(
                    token_digits, self._written_digits) if run == digits)]

    # ═══ THE REPORTING DIRECTION ═══════════════════════════════════════════
    # Три вопроса выше отвечают «ЧЬЯ это подмена» и молчат, когда кандидатов
    # несколько или единственный живёт в чужом разговоре. Это молчание и есть
    # отказ: подмена остаётся стоять, и в инструмент уходит фейк при 200. Ниже
    # — те же три запроса, заданные в обратную сторону: «наше ли это вообще»,
    # без требования единственности, по всему заказчику. Диагностика, которая
    # подчинялась бы области, о которой докладывает, не доложила бы ничего —
    # отказ по ЧУЖОМУ диалогу самый частый из всех, — а наружу такой ответ
    # отдаёт только «да/нет» про нашу же подмену, ни одного значения.
    #
    # ВОПРОС ЗАДАЁТСЯ О ТОМ, ЧТО НАПИСАЛ АГЕНТ, И ТОЛЬКО О НЁМ. Спрошенный о
    # ВОССТАНОВЛЕННОМ тексте, он поднимает тревогу на правильном ответе:
    # настоящая улица, случайно делящая основу с двумя нашими подменами,
    # отвечает «да» — 5 ложных тревог на 50 диалогах документированного
    # клиента. Кто спрашивает — `redact.surviving_substitutes`, и он же проверяет,
    # что фрагмент ВСЁ ЕЩЁ СТОИТ в ответе: разрешившийся из ответа исчез.

    def place_fragment_is_ours(self, candidate: str, role: str = "") -> bool:
        """Хоть одна адресная подмена этого заказчика носит ВСЕ части этого
        фрагмента — «наше это слово (или число), или клиентское».

        Покрывает оба класса адресного фрагмента одним вопросом: название улицы
        без дома и НОМЕР ДОМА без улицы. Второй до сих пор отказывал молча — 22
        из 50 у документированного клиента, — потому что вопрос о нём вовсе не
        задавался: ключ с цифрами исключался как «отвечающий по всему
        заказчику», а это про ОБЛАСТЬ, а не про единственность.

        РОЛЬ — ЧАСТЬ ВОПРОСА, А НЕ УКРАШЕНИЕ. `token_parts` держит части
        подмены без роли, потому что на прямом пути роль не нужна: «47» ищется
        как «47». Но спрошенный ролью, этот индекс отвечает НЕ О ТОМ: поле
        `flat` с числом 26 находило подмену, у которой 26 — НОМЕР ДОМА, и
        сигнал называл нашим значение, которое восстановление даже не пыталось
        заменить (роль оно проверяет, см. `_restore_cued_numbers_spans`). Замер
        документированного клиента: 10 из 21 ложных тревог — ровно этот класс,
        квартиры, которых ни в одной подмене нет. Роль читается из имени поля
        (`role_of_field`) или из подсказки в прозе («кв. 26»), и владелец
        обязан носить кусок ИМЕННО В НЕЙ.
        """
        stems, numbers = morph_places.signature_parts(candidate)
        parts = [*stems, *numbers]
        if not parts:
            return False
        owners, truncated = self._loc_parts_owners(parts)
        if not truncated and owners and role:
            # ПЕРВОГО ПОДХОДЯЩЕГО ХВАТАЕТ, и это не мелочь: вопрос «наше ли»
            # не спрашивает, ЧЬЁ, а у распространённой основы владельцев до
            # полусотни, и каждый стоит разбора адреса. Ответ «да» находится
            # на первом; полный перебор платит только отрицательный ответ.
            return any(_wears_parts_in_role(token, stems, numbers, role)
                       for token in owners)
        # ДВА ЗАПРОСА, А НЕ ОДИН JOIN, И ЭТО РАЗНИЦА В ШЕСТЬСОТ РАЗ. Совмещённый
        # запрос `place_owner` идёт по `idx_tokens_namekey (customer=?)`, то есть
        # перебирает ВСЕ строки заказчика: 55 мс на 60 000 строк за одну основу.
        # Восстановление платит это один раз за ответ, а сигнал спрашивает на
        # КАЖДЫЙ уцелевший кандидат — тем же планом он стоил бы вчетверо
        # дороже всего восстановления (замер: 0.5 → 2.0 с на 60 000 строк).
        #
        # ОБРЕЗАННОЕ ЧТЕНИЕ — ЭТО «НЕ ЗНАЮ», И ЗДЕСЬ ОНО ЗНАЧИТ «ПОКАЖИ».
        # Молчание — это фейк в инструменте при 200; лишняя строка в списке —
        # повод перепроверить вызов. Та же безопасная сторона, в которую
        # поворачивает от потолка `_sole_place_owner`.
        return truncated or bool(owners)

    def digit_fragment_is_ours(self, fragment: str, entity_type: str | None = None,
                               position: str | None = None) -> bool:
        """Цифры этого куска стоят НА КРАЮ цифр хоть одной подмены этого
        заказчика — последние четыре цифры телефона, серия паспорта, группа
        СНИЛС. Тот же отбор, что у `digit_fragment_owner` (кусок строго короче
        значения, длины настоящего и подменного совпадают, край назван), без
        требования единственности.

        ТИП И МЕСТО — ТО ЖЕ СУЖЕНИЕ, ЧТО У ВОССТАНОВЛЕНИЯ. `digit_fragment_owner`
        никогда не спрашивает «стоит ли этот кусок хоть где-нибудь»: подсказка
        говорит, ЧЕЙ это кусок и с какого он края («серия 4509» — начало
        паспорта, «контрольное число 59» — конец СНИЛС). Спрошенный без
        сужения, вопрос отвечает «да» почти на любые две цифры — телефон несёт
        одиннадцать, и внутри них стоит половина двузначных чисел на свете.
        Сигнал обязан спрашивать ровно то, что спросило восстановление, иначе
        он докладывает об отказе, которого не было.

        СВОЙ ЗАПРОС С ПРЕДЕЛОМ, А НЕ ЧУЖОЙ БЕЗ НЕГО. `instr` по подстроке не
        ложится ни на один индекс, поэтому поиск куска — это перебор строк
        заказчика; `digit_fragment_owner` платит его, потому что обязан увидеть
        ВТОРОГО кандидата, чтобы отказать. Здесь достаточно первого, и предел
        обрывает чтение на нём. Промах всё равно читает всё — но ровно столько
        же читает и восстановление, которое уже спросило про этот же кусок."""
        digits = "".join(ch for ch in fragment if ch.isdigit())
        if len(digits) < 2:
            return False
        with self._lock:
            rows = self._conn.execute(
                "SELECT digits, entity_type, canonical, original FROM tokens "
                "WHERE customer=? AND digits IS NOT NULL "
                "AND length(digits) > ? AND instr(digits, ?) > 0 LIMIT ?",
                (self._customer, len(digits), digits, _DIGIT_FRAGMENT_PROBE),
            ).fetchall()
        # ВЕТО НЕ ФИЛЬТРУЕТСЯ ЗДЕСЬ, И ЭТО НЕ РАСХОЖДЕНИЕ С ВОССТАНОВЛЕНИЕМ
        # (Б29). Ветированная подмена (`with_spent_signatures`) — ровно тот
        # случай, когда восстановление ОТКАЗАЛО: кусок стоит на краю подмены,
        # которую агент написал в этом же вызове целиком, и в инструмент уходит
        # фейковый хвост. Здесь стоял пропуск такой строки — и отказ получался
        # МОЛЧАЛИВЫМ: схема, просящая телефон и его последние четыре цифры,
        # отдавала фейк при 200 и пустом остатке, чего заказчик не узнаёт
        # никогда. Порядок тяжести валют прямой: молчаливая потеря хуже
        # названной, а названная хуже ложной тревоги. Молчать о состоявшемся
        # отказе нельзя — вето остаётся, но оно говорит.
        for token_digits, row_type, canonical, original in rows:
            if entity_type is not None and row_type != entity_type:
                continue
            value = _pick_value(row_type, canonical or "", original or "", True)
            real = "".join(ch for ch in value if ch.isdigit())
            # Разной длины — смещение не переносится, и восстановление такую
            # строку тоже пропускает; сообщать о ней было бы ложной тревогой.
            if len(real) != len(token_digits):
                continue
            # КРАЙ ИЛИ ПЛИТКА — ТО ЖЕ УСЛОВИЕ И ТОТ ЖЕ КОД, ЧТО У
            # ВОССТАНОВЛЕНИЯ (Б29). Здесь стояло «`position is None` — значит
            # да», то есть «кусок лежит внутри цифр хоть чего-нибудь»;
            # восстановление такую строку больше не трогает, значит отказа нет
            # и называть нечего. Оставленное как было, это давало ложную
            # тревогу на КАЖДОМ артикуле и количестве заказчика: вызов верен, а
            # шлюзу сказано «не исполняй» — 191 из 2880 на приборе кусков.
            if _placements(token_digits, digits, position) or any(
                    run == digits for _at, run in _tiling(
                        token_digits, self._written_digits)):
                return True
        return False

    def date_reading_is_ours(self, reading: str) -> bool:
        """Хоть одна подмена даты этого заказчика индексирована под этим
        прочтением. Дата — такой же фрагмент, как улица: агент переписывает её
        в свою нотацию, точная подмена больше не совпадает, и без этого вопроса
        отказ был бы так же нем.

        ДВА ЗАПРОСА, А НЕ JOIN, ПО ТОЙ ЖЕ ПРИЧИНЕ, ЧТО У `place_fragment_is_ours`:
        совмещённый запрос `date_owner` ведёт по `tokens` и перебирает все
        строки заказчика — 63 мс на 60 000 строк, и спрашивается он на каждое
        прочтение даты в ответе. Здесь — покрывающий индекс (customer, part) и
        точечная проверка типа."""
        if not reading:
            return False
        with self._lock:
            named = [row[0] for row in self._conn.execute(
                "SELECT token FROM token_parts WHERE customer=? AND part=? LIMIT ?",
                (self._customer, reading, _PLACE_OWNER_CAP + 1),
            ).fetchall()]
            if not named:
                return False
            row = self._conn.execute(
                "SELECT 1 FROM tokens WHERE customer=? AND entity_type IN ('DOB','DATE') "
                f"AND token IN ({','.join('?' * len(named))}) LIMIT 1",
                (self._customer, *named),
            ).fetchone()
        return row is not None

    def residual_of(self, candidate: str) -> str | None:
        """The minted token this leftover string is a piece of, if any.

        A model that writes «Юлия Тарасова» for the token «Тарасова Юлия
        Петровна», or just «Юлия», produces a string that resolves to nothing —
        so the FAKE goes to the customer's tool with a 200 and an empty log. The
        words are still ours, and that is what this asks: does every word of the
        candidate belong to ONE substitute we minted for this customer.

        EVERY word must match, and they must agree on one token. A single shared
        word would fire on a real customer who happens to be called Юлия, and a
        warning that cries on ordinary traffic is a warning nobody reads.
        """
        words = [word for word in candidate.split() if len(word) > 2]
        if not words and len(candidate.split()) == 1 and len(candidate.strip()) == 2:
            # «Ян», «Ия» — a whole field of two letters is a name, not a
            # particle. The filter exists for «на» and «по» INSIDE a phrase.
            words = [candidate.strip()]
        if not words:
            return None
        with self._lock:
            owners: list[set[str]] = []
            for word in words:
                if word.isascii():
                    # A LATIN WORD IS LOOKED UP FOLDED, never by its letters:
                    # the index holds one canonical spelling per fake word and
                    # the model may have chosen any rendering of it. Morphology
                    # has nothing to say about a Latin string.
                    forms = [translit.fold(word)]
                else:
                    # BOTH GENDERS' NOMINATIVES. The token is minted in the nominative
                    # («Наумов Лев Евгеньевич») and shown to the model inflected («Наумова
                    # Льва Евгеньевича»); the model copies the surname as it read it into
                    # `last_name`, and «Наумова» is a woman's nominative as well as a man's
                    # genitive, so `to_nominative` — rightly — leaves it alone while the index
                    # holds «наумов». Measured on the scripted agent: every oblique surname
                    # argument went to the tool as the fake.
                    variants = {word.casefold(), morph_names.to_nominative(word).casefold()}
                    for gender in ("masc", "femn"):
                        variants.add(morph_names._part_to_nominative(word, gender).casefold())
                    forms = sorted(variants)
                # ТОЛЬКО ИМЕНА. Таблица частей общая с адресами с тех пор, как
                # адресный фрагмент стал разрешаться, и без фильтра одиночное
                # слово адресной подмены находило владельца ЗДЕСЬ — мимо области
                # разговора и мимо урезания до названных частей. Наружу это
                # выглядело так: лист `street` со значением «переулок Рябиновый»
                # возвращался как «переулок переулок загородный двадцать два» —
                # родовое слово осталось от подмены, а следом встал весь
                # настоящий адрес.
                rows = self._conn.execute(
                    "SELECT t.token FROM token_parts AS t "
                    "JOIN tokens AS k ON k.customer=t.customer AND k.token=t.token "
                    "WHERE t.customer=? AND k.entity_type='NAME' AND t.part IN "
                    f"({','.join('?' * len(forms))})",
                    (self._customer, *forms),
                ).fetchall()
                if not rows:
                    return None
                owners.append({row[0] for row in rows})
        shared = set.intersection(*owners)
        if not shared:
            return None
        # ONLY A SUBSTITUTE THIS CONVERSATION WAS SHOWN. A single owner across
        # the customer's whole vault used to win outright, and «николая» in a
        # street name the customer wrote in the clear resolved to the one
        # dialogue, a week earlier, that had drawn «Николай Крылов» — the
        # tool received another person (known-issues Б23). The model can only
        # write a piece of what it read HERE, so `token_uses` decides: one
        # owner shown here wins, none means the word is the customer's own,
        # several fall to the tie-breaks below. Without a conversation scope
        # nothing has changed.
        if self._conversation:
            rows = self._conn.execute(
                "SELECT token FROM token_uses WHERE customer=? AND conversation=? "
                f"AND token IN ({','.join('?' * len(shared))})",
                (self._customer, self._conversation, *sorted(shared)),
            ).fetchall()
            here = {row[0] for row in rows}
            if len(here) == 1:
                return next(iter(here))
            if not here:
                return None
            shared = here
        if len(shared) == 1:
            return next(iter(shared))
        one = self._one_identity(shared)
        if one is not None:
            return one
        # THE CONVERSATION BREAKS THE TIE. A pair of initials is two letters,
        # a given name in Latin is «Anna»: across a customer's whole vault
        # such a piece belongs to many substitutes, and «no single owner»
        # returned None — the fake went to the CRM with a 200 («Т.О.» for a
        # woman whose initials are А.И., on the 05.09 medium run, where the
        # same vault had served a thousand dialogues). The model writes the
        # piece INSIDE the dialogue that handed it the substitute, which is
        # exactly what `minted_in` records; a piece shared by two substitutes
        # of ONE conversation stays unresolved, because then the dialogue
        # itself cannot say which person it means.
        if not self._conversation:
            return None
        rows = self._conn.execute(
            "SELECT token FROM tokens WHERE customer=? AND minted_in=? "
            f"AND token IN ({','.join('?' * len(shared))})",
            (self._customer, self._conversation, *sorted(shared)),
        ).fetchall()
        here = {row[0] for row in rows}
        return next(iter(here)) if len(here) == 1 else None

    def _same_person_reordered(self, canonical: str) -> str | None:
        """The token of a person already on file, written in another word order.

        «Гончарова Анна Дмитриевна» and «Анна Дмитриевна Гончарова» are one
        customer: a form asks for «Фамилия Имя Отчество», a person says «Имя
        Фамилия». Keyed by the written order they were two rows, so the model met
        two people and «один человек — один токен» did not hold. A persona
        measured seven spellings of one client and counted seven substitutes.

        Matched HERE and not in `canonicalize`, because that function also
        decides what `detokenize` hands the tool: sorting the parts into slots
        there made «Клиент Елена Попова» come back as «Клиент Попова Елена». The
        customer's word order is part of the value. It is not part of the person.

        Uses `name_parts`, which is already indexed and already populated for
        every multi-word name, so this costs one query and no new storage. A row
        qualifies only when its parts are the SAME MULTISET — a subset would
        merge «Иванов Пётр» into «Иванов Пётр Сергеевич», and merging two people
        is the one failure this product treats as unacceptable.
        """
        parts = [word.casefold() for word in canonical.split() if len(word) > 2]
        if len(parts) < 2:
            return None
        rows = self._conn.execute(
            "SELECT t.canonical, t.token FROM name_parts p "
            "JOIN tokens t ON t.customer = p.customer AND t.canonical = p.canonical "
            "WHERE p.customer=? AND p.part=? AND t.entity_type='NAME'",
            (self._customer, parts[0]),
        ).fetchall()
        wanted = sorted(parts)
        matches = {token for other, token in rows
                   if sorted(word.casefold() for word in other.split()
                             if len(word) > 2) == wanted}
        return next(iter(matches)) if len(matches) == 1 else None

    def _expire_place_parts(self) -> None:
        """Drop conversation links older than a day. Called under the lock."""
        global _last_place_sweep
        now = time.time()
        if now - _last_place_sweep < _PLACE_SWEEP_INTERVAL:
            return
        _last_place_sweep = now
        self._conn.execute("DELETE FROM place_parts WHERE created < ?",
                           (now - _PLACE_PART_TTL,))
        self._conn.execute("DELETE FROM token_uses WHERE created < ?",
                           (now - _PLACE_PART_TTL,))
        self._conn.execute("DELETE FROM shown_forms WHERE created < ?",
                           (now - _PLACE_PART_TTL,))

    def _place_rows(self, part: str, has_city: int | None) -> list:
        """This conversation's indexed places whose short key names the same
        street and house as `part` — exactly, or one typo apart in the street
        (`_keys_match`). A conversation holds a handful of places, so the
        rows are read once and compared in Python rather than by `=`. Returns
        (canonical, token) pairs, or (has_city, canonical, token) triples when
        `has_city` is None."""
        rows = self._conn.execute(
            "SELECT p.has_city, p.canonical, p.part, t.token FROM place_parts p "
            "JOIN tokens t ON t.customer = p.customer AND t.canonical = p.canonical "
            "WHERE p.customer=? AND p.conversation=? AND t.entity_type='LOC' LIMIT 64",
            (self._customer, self._conversation),
        ).fetchall()
        matched = [(city_flag, owner, token) for city_flag, owner, stored, token in rows
                   if _keys_match(stored, part) and (has_city is None or city_flag == has_city)]
        if has_city is None:
            return matched
        return [(owner, token) for _, owner, token in matched]

    def _same_street_in_conversation(self, value: str, shape: dict[str, object]) -> str:
        """The fake street phrase this conversation already uses for the REAL
        street this mention names — at another house — or "".

        «заречная пятьдесят семь … ой нет, правильно заречная двадцать девять»
        minted «Черёмуховая 15» and «Грушевая 107»: two streets where the
        customer corrected a house number, and the model read a correction
        between two unrelated places (32 of the 36 `correction` cases with two
        addresses on the seed-6060 run name one street). One real street in a
        dialogue is one fake street; only the numbers differ, exactly as they
        do in the customer's own words. The street stems are compared the way
        `_keys_match` compares them — equal, or one typo apart — because the
        correction is often OF the typo («ленна» → «ленина»). Two different
        fake streets already standing for the same stem (minted before this
        rule, or through the second-half fallback) mean no head: guessing
        between them would be the very thing this avoids.
        """
        if not self._conversation or not shape.get("has_house"):
            return ""
        part = morph_places.street_house_key(value)
        stem = _street_stem(part)
        if not stem:
            return ""
        # THE SAME SETTLEMENT, OR NONE ON EITHER SIDE. «Луговая» in Колпино and
        # «Луговая» in Ижевск are two streets: a directory that answers the
        # customer's «луговая 9» with a record from another city shared the
        # fake street with it, and the model — asked to compare — could no
        # longer see they differ (r2 run, compare-012). The same rule
        # `_same_place_written_differently` applies to the whole place.
        settlement = _settlement_of(value).casefold() if shape.get("has_city") else ""
        rows = self._conn.execute(
            "SELECT p.part, p.has_city, p.canonical, t.token FROM place_parts p "
            "JOIN tokens t ON t.customer = p.customer AND t.canonical = p.canonical "
            "WHERE p.customer=? AND p.conversation=? AND t.entity_type='LOC' LIMIT 64",
            (self._customer, self._conversation),
        ).fetchall()
        heads: set[str] = set()
        for stored, city_flag, canonical, token in rows:
            # ОДНА УЛИЦА — ОДНА ПОДМЕННАЯ УЛИЦА, НЕЗАВИСИМО ОТ ДОМА. Здесь стоял
            # ещё и пропуск «stored == part» — то есть ровно та строка, чей
            # терпимый ключ совпал, ИСКЛЮЧАЛАСЬ из поиска головы. Совпадает же
            # он именно у соседних домов одной улицы: `street_house_key` срезает
            # приклеенную литеру, и «9а» даёт тот же ключ, что «9». Дом 9а
            # получал НОВУЮ подменную улицу, следующий дом — ещё одну: одна
            # улица → N подмен, и в инструмент уезжали три несвязанных адреса
            # (g06/search_rank P3 — четыре подмены на «депутатской»). Правило
            # переиспользования читается по ОСНОВЕ улицы, и совпавший ключ — это
            # «та же улица», а не повод её пропустить; различать надо ДОМА, и
            # различает их `_shares_a_house_in_conversation` при чеканке.
            if not _street_stems_match(_street_stem(stored), stem):
                continue
            other_settlement = canonical.split()[0].casefold() if city_flag else ""
            if settlement != other_settlement:
                continue
            fake_head = morph_places.split_roles(token).get("street", "")
            if fake_head:
                heads.add(fake_head)
        return next(iter(heads)) if len(heads) == 1 else ""

    def _same_place_written_differently(self, canonical: str, value: str,
                                        shape: dict[str, object]) -> tuple[str, str] | None:
        """The substitute for an address this conversation already holds with
        the same settlement, street and house — written another way.

        «Самара, Луговая 10» from the customer and «Самарская область, г
        Самара, ул Луговая, д 10» back from the directory are one place, and
        the canonical keeps them apart on purpose. What it may not do is mint a
        second substitute for one place — the model then compares the address
        it asked about with a different fake and answers «не найден» (live v4,
        `compare`: 29 of 42 triples).

        ЭТО И ЕСТЬ ОТДЕЛЬНОЕ ПРАВИЛО СВЯЗЫВАНИЯ ДЛЯ ТИПА, которого требует
        решение владельца. Родовое слово — часть тождества, поэтому «переулок
        Мончегорская 10» и «Мончегорская 10» — две строки; связываются они
        ЗДЕСЬ, по основе улицы, дому и городу, а не по ключу, и одно место
        по-прежнему получает одну подмену (A2). Обратная сторона той же монеты:
        два РАЗНЫХ типа, названных оба («переулок Пушкина» и «улица Пушкина»),
        — это два места, и связывать их нельзя ничем; поэтому тип сравнивается
        отдельно и только когда он назван С ОБЕИХ сторон.

        Same discipline as every link here: exactly one owner on that street
        and house in this conversation, AND the same settlement — a different
        city on the same street and house is a different place and gets its own
        substitute.

        БЕЗ РАЗГОВОРА ЭТОТ ЖЕ ВОПРОС ЗАДАЁТСЯ ПО САМОМУ КЛЮЧУ. «Одно место — одна
        подмена навсегда и между разговорами» — записанный контракт
        (`bench/agentpii5/test_mint_consistency`), а `place_parts` живёт только
        внутри разговора. Поэтому, когда разговора нет вовсе (или в разговоре
        пары не нашлось), та же пара ищется `_place_family_owner`: тип стоит
        ПОСЛЕДНИМ слотом ключа, значит написание без типа — префикс написания с
        типом, и продолжение читается диапазоном по индексу.
        """
        found = self._place_family_owner(canonical)
        if found is not None:
            return found, found
        if not self._conversation:
            return None
        part = morph_places.street_house_key(value)
        if not part:
            return None
        # ОБА ВИДА СТРОК: с городом и без. Город входит в тождество
        # (`_place_identity`), поэтому пара «с городом / без города» не
        # встретится здесь никогда — её разбирает `_linked_place`.
        rows = self._place_rows(part, has_city=None)
        # THE WHOLE IDENTITY MINUS THE TYPE WORD: settlement, street stem and
        # every number as written. The short key drops the house litera on
        # purpose (a short mention may omit it), and read alone it linked the
        # register's NEIGHBOUR — «д 10А» to «д 10» — into one substitute.
        wanted = _place_identity(canonical)
        named = morph_places.key_type(canonical)
        same = [token for _city, owner_canonical, token in rows
                if _same_house(_place_identity(owner_canonical), wanted)
                and not (named and morph_places.key_type(owner_canonical)
                         and named != morph_places.key_type(owner_canonical))]
        if len(same) != 1:
            return None
        return same[0], same[0]

    def _place_family_owner(self, canonical: str) -> str | None:
        """Подмена этого заказчика, чей ключ отличается только СЛОТОМ ТИПА.

        «г. Уфа, переулок Мончегорская 10, кв. 54» и «г. Уфа, Мончегорская 10,
        кв. 54» — одно место, и одно место обязано остаться одной подменой и
        между разговорами (`bench/agentpii5/test_mint_consistency`). Тип —
        ПОСЛЕДНИЙ слот `address_key`, поэтому написание без типа есть префикс
        написания с типом, и вопрос задаётся ДВУМЯ точечными чтениями по
        индексу `(customer, canonical)`, а не перебором строк заказчика.

        РОВНО ОДНО ПРОДОЛЖЕНИЕ — ЭТО ОДНО МЕСТО. Два («переулок» и «улица» на
        той же основе, доме и городе) — два разных места по решению владельца, и
        ответа нет: назвать любое из них значило бы отправить курьера не туда.

        БЕЗ `self._lock`: вызывается только из чеканки, которая лок уже держит
        (`threading.Lock` не реентрантный — тот же урок, что у
        `_real_place_with_stem_locked`).
        """
        words = canonical.split()
        base = [word for word in words if word not in morph_places._GENERIC]
        if not base:
            return None
        plain = " ".join(base)
        # НАПИСАНИЯ С ТИПОМ НА ЭТОЙ ЖЕ ОСНОВЕ — это «plain <пробел> тип».
        # Диапазон начинается с пробела, поэтому «plainfoo» в него не попадает.
        typed_rows = self._conn.execute(
            "SELECT canonical, token FROM tokens WHERE customer=? AND entity_type='LOC' "
            "AND canonical >= ? AND canonical < ? LIMIT 2",
            (self._customer, plain + " ", plain + " \uffff"),
        ).fetchall()
        if len(base) == len(words):
            # БЕЗ ТИПА: ровно одно продолжение — это одно место; два («переулок»
            # и «улица») — два разных места, и ответа нет.
            return typed_rows[0][1] if len(typed_rows) == 1 else None
        # С ТИПОМ: ДРУГОЙ ТИП НА ТОЙ ЖЕ ОСНОВЕ ЗАКРЫВАЕТ ВОПРОС. «переулок
        # Пушкина 5» и «улица Пушкина 5» — два места (решение владельца), и
        # связать второе с бестиповой строкой, которую занял первый, значило бы
        # слить их в одну подмену.
        mine = frozenset(morph_places.key_type(canonical))
        if any(frozenset(morph_places.key_type(other)) != mine
               for other, _token in typed_rows):
            return None
        rows = self._conn.execute(
            "SELECT token FROM tokens WHERE customer=? AND entity_type='LOC' "
            "AND canonical=?",
            (self._customer, plain),
        ).fetchall()
        return rows[0][0] if len(rows) == 1 else None

    def holds_minted_place(self, value: str) -> bool:
        """A LOC mention that CONTAINS a substitute of this conversation.

        The model was handed «улица Мятная 151» and, told the city in the
        clear, wrote «Самара, улица Мятная 151» into its tool call. That call
        rides in the transcript and is re-masked with it on the next request —
        production behaviour, the role of a message is not evidence — and the
        composition is a well-formed address that `is_minted_token` cannot
        recognise because it is not exactly the token. It was minted AGAIN, so
        the model saw its own query rewritten into a third address a turn
        later. Nothing in the composition is new to the model: the city is one
        it was already shown, the rest is ours. So it is left as written.

        Scoped to the conversation that minted the token, like the guard it
        extends; a caller that named none gets nothing here, because outside a
        conversation the composition cannot be told from a real address.
        """
        if not self._conversation:
            return False
        with self._lock:
            rows = self._conn.execute(
                "SELECT token FROM tokens WHERE customer=? AND entity_type='LOC' "
                "AND minted_in=?",
                (self._customer, self._conversation),
            ).fetchall()
        key = morph_places.street_house_key(value)
        if key:
            return any(morph_places.street_house_key(token) == key for (token,) in rows)
        # УЛИЦА БЕЗ ДОМА — ЭТО НАША ПОДМЕНА, РАЗОБРАННАЯ ЧУЖИМ ИНСТРУМЕНТОМ.
        # `normalize_contact` (и любой DaData-подобный нормализатор в стеке
        # заказчика) отдаёт адрес ПО ЧАСТЯМ: «Сортавала, переулок Кедровый» в
        # одном поле, «160» в другом. Ключ выше требует дома, поэтому у части
        # его нет; точечная защита не срабатывает, потому что это не токен
        # дословно, — и подмена маскируется ВТОРОЙ раз, новым фальшивым
        # адресом, у которого нет владельца. Дальше в инструмент заказчика
        # уезжает фейк: 198 из 328 расхождений скриптового прогона и −78pp у
        # семьи `normalize`.
        #
        # ЦЕНА — ТА ЖЕ, ЧТО У КЛЮЧА ВЫШЕ, И ОГРАНИЧЕНА ТЕМ ЖЕ РАЗГОВОРОМ:
        # настоящая улица, совпавшая с нашей фальшивой, ушла бы к модели
        # открытой. `_unique_token` уже отказывает кандидату, равному любому
        # `canonical` заказчика, поэтому совпасть может только улица, названная
        # ПОЗЖЕ, и только внутри одной беседы.
        stem = _street_stem(value)
        return bool(stem) and any(_street_stem(token) == stem for (token,) in rows)

    def _linked_place(self, canonical: str, value: str,
                      shape: dict[str, object]) -> tuple[str, str] | None:
        """The substitute for an address we already met, named more briefly.

        «вы находитесь на Ленина 14?» while the fuller «г. Москва, ул. Ленина,
        д. 14» stands in the same conversation. They key differently, so the
        model was handed two different fake addresses and asked to compare them
        — it duly answered that no, those are not the same place. Nothing in the
        pipeline was broken; the two mentions simply had no way to be one thing.

        The answer is the same one names already use: not a second random
        address and not the full one, but the CORRESPONDING PART of the
        substitute this place already has. A mention that named no city gets
        back a substitute with no city.

        LINKED ONLY WHEN THERE IS EXACTLY ONE OWNER. This is Fellegi–Sunter's
        middle outcome — «possible link, refer to a human» — and a gateway has
        no human, so it collapses to refusal. Two addresses on the same street
        in one conversation (home and delivery) means neither links, and the
        behaviour is what it was before this existed. Guessing instead would
        send a courier to the wrong one of two real places, which is worse than
        the model seeing two addresses.

        WHY NOT COMPONENT-WISE. Substituting city, street and house through
        separate deterministic maps would make «Ленина 14» in Moscow and in
        Kazan share a substitute by construction — prefix-preserving
        anonymisation, and Xu et al. proved that every scheme with that property
        leaks the shared prefix once any one element is compromised. The
        single-owner rule gets the linking without the property.
        """
        if not self._conversation:
            return None
        part = morph_places.street_house_key(value)
        if not part:
            return None
        # A mention that already names a city is not a short one — it is either
        # the full address (found by the canonical lookup) or a different place.
        if shape.get("has_city"):
            return None
        # ONLY A CITY-BEARING ROW OWNS A SHORT MENTION. City-less mentions are
        # indexed too now (so a later fuller form can grow them), and without
        # this filter the short form would be its own owner.
        rows = self._place_rows(part, has_city=1)
        # Candidates by the tolerant key, the decision by the exact house
        # (see `_house_identity`): the register's «д 10» and «д 10А» are two
        # owners of one key and one owner of «луговая 10».
        wanted = _house_identity(canonical, False)
        owners = [token for owner_canonical, token in rows
                  if _same_house(_house_identity(owner_canonical, True), wanted)]
        if len(owners) != 1:
            return None
        full = owners[0]
        derived = morph_places.strip_leading_city(full)
        if not shape.get("has_flat"):
            derived = morph_places.strip_flat(derived)
        # A projection identical to the full token is not a projection: the
        # stored address had no city either, so there is nothing shorter to
        # render and the two mentions are the same string anyway.
        return (derived, full) if derived else None

    def _extends_linked_place(self, canonical: str, value: str,
                              shape: dict[str, object]) -> tuple[str, str] | None:
        """The mirror of `_linked_place`: a FULLER mention arriving after a
        shorter one in the same conversation.

        «центральная сто» from the customer, then «Краснодар, центральная,
        100» from the address directory the model asked — one place, and the
        model was handed two substitutes and could not match what it had just
        asked for (live v4: 30 of 42 `compare` triples, twice a NEIGHBOUR's
        record picked instead). The full substitute is GROWN from the short
        one: same head and house, a fake city in front, the tails the fuller
        mention names — so the short token stays a literal substring of the
        full one and a later short mention links straight back.

        Single owner or nothing, read across both kinds of rows: a city-bearing
        address on the same street and house in this conversation means the
        fuller mention is a different place (the canonical lookup would have
        found the same one), and two short candidates mean a guess.
        """
        if not self._conversation or not shape.get("has_city"):
            return None
        part = morph_places.street_house_key(value)
        if not part:
            return None
        rows = [(has_city, owner, token) for has_city, owner, token in self._place_rows(part, has_city=None)]
        wanted = _house_identity(canonical, True)
        # A city-bearing row on this EXACT street and house is another town's
        # (the same town would have been found by `_same_place_written_
        # differently`), and then the short mention is a guess between the two.
        if any(has_city == 1 and _same_house(_house_identity(owner, True), wanted)
               for has_city, owner, _ in rows):
            return None
        shorts = [token for has_city, owner, token in rows
                  if has_city == 0 and _same_house(_house_identity(owner, False), wanted)]
        if len(shorts) != 1:
            return None
        short = shorts[0]
        if morph_places.strip_leading_city(short) != short:
            return None
        grown = _extend_place(short, value, shape)
        if grown is None or not re.fullmatch(LOC_TOKEN_PATTERN, grown):
            return None
        if not self._is_free_token(grown, "LOC", value, canonical):
            return None
        return grown, short

    def _linked_token(self, canonical: str, surface: str) -> tuple[str, str] | None:
        """The substitute for a person we have already met, named more briefly.

        «Иванов Пётр Сергеевич» in one turn and «Петру» in the next are the same
        person, and the product's own claim is that the model sees one person.
        They used to key differently — a full name canonicalises to itself, a
        bare given name to itself — so the model met two.

        The answer is not a second random name and not the full one: it is the
        CORRESPONDING PART of the substitute that person already has. If Иванов
        Пётр Сергеевич became Сазонов Олег Андреевич, then Пётр becomes Олег.
        That satisfies both rules at once — same identity, and a one-word mention
        still gets one word.

        LINKED ONLY WHEN UNAMBIGUOUS. Two people named Пётр on file means neither
        is linked: merging two customers into one sends the wrong person's data
        to a tool, which is worse than the model seeing two. The asymmetry is
        deliberate — consistency is quality, identity is correctness.

        MATCHED BY CANONICAL AND BY SURFACE, in that order. The canonical reaches
        an inflected mention («Петру» → «Пётр»); the surface reaches one where
        canonicalisation itself is what lost the person. «Иванова», written after
        «фамилия» and standing alone, reduces to «Иванов» — a name that is not in
        this woman's file at all — so the canonical lookup found nothing and she
        got a second identity. Her surname IS in the file, spelled exactly as she
        wrote it, as a part of the full name from the first turn.

        The surface path still earns its place now that `canonicalize` keeps a
        lone «Иванова» as itself. A vault written before that change holds her
        under «Иванов»; the canonical lookup for a new mention now derives
        «Иванова» and misses it, and the surface match against `name_parts` is
        what still reaches her file. Where no full name was ever stored she does
        get a second row — a one-time split at the upgrade boundary, which is
        the quality side of the trade, not the correctness one.
        """
        candidates: list[str] = []
        parts = canonical.split()
        if len(parts) == 1 and len(parts[0]) > 2:
            candidates.append(parts[0])
        stripped = surface.strip()
        if len(stripped.split()) == 1 and len(stripped) > 2:
            candidates.append(stripped)
        for candidate in candidates:
            rows = self._conn.execute(
                "SELECT t.canonical, t.token FROM name_parts p "
                "JOIN tokens t ON t.customer = p.customer AND t.canonical = p.canonical "
                "WHERE p.customer=? AND p.part=? AND t.entity_type='NAME' LIMIT 2",
                (self._customer, candidate.casefold()),
            ).fetchall()
            if len(rows) == 2:
                # Two rows that are ONE person — the two-word mention and the
                # three-word one grown from it — are not an ambiguity.
                fullest = self._one_identity({token for _, token in rows})
                rows = [row for row in rows if row[1] == fullest] if fullest else rows
            if len(rows) != 1:
                continue
            full_canonical, full_token = rows[0]
            derived = _corresponding_part(candidate, full_canonical, full_token)
            if derived is None or derived == full_token:
                continue
            # The derived word must not already stand for somebody else.
            clash = self._conn.execute(
                "SELECT 1 FROM tokens WHERE customer=? AND token=? LIMIT 1",
                (self._customer, derived),
            ).fetchone()
            if clash:
                continue
            return derived, full_token
        return None

    def _extends_known_person(self, canonical: str, value: str,
                              gender: str | None) -> tuple[str, str] | None:
        """A FULLER name after a shorter one, in the same conversation, reuses
        the substitute's parts.

        «букин сергей» in the user's turn, «Букин Сергей Иванович» in the CRM
        record a tool returns — one person, two substitutes, and the model
        joined them into a double surname (live v4, `container`). The
        subset rule stays forbidden at customer scope (see
        `_same_person_reordered`); it is licensed here by THREE things at once:
        the same conversation (`minted_in`, exactly — a row that does not know
        its conversation is not linked by one), a strict superset of the parts
        of a ≥2-word name, and exactly one candidate. The known parts take the
        substitute's words of the same kind; the new part (a patronymic) is
        drawn fresh; the whole must survive its own inflection and the same
        guards a random draw passes.
        """
        parts = [word.casefold() for word in canonical.split() if len(word) > 2]
        if len(parts) < 3 or not self._conversation:
            return None
        rows = self._conn.execute(
            "SELECT DISTINCT t.canonical, t.token FROM name_parts p "
            "JOIN tokens t ON t.customer = p.customer AND t.canonical = p.canonical "
            "WHERE p.customer=? AND t.entity_type='NAME' AND t.minted_in=? "
            f"AND p.part IN ({','.join('?' * len(parts))})",
            (self._customer, self._conversation, *parts),
        ).fetchall()
        wanted = set(parts)
        candidates = {(other, token) for other, token in rows
                      if 2 <= len([w for w in other.split() if len(w) > 2])
                      and set(w.casefold() for w in other.split() if len(w) > 2) < wanted}
        tokens = {token for _, token in candidates}
        if len(tokens) != 1:
            return None
        short_canonical, short_token = next(iter(candidates))
        real_parts = canonical.split()
        shape = morph_names.name_shape(canonical)
        if len(shape) != len(real_parts):
            return None
        resolved = gender if gender in ("masc", "femn") else morph_names.detect_gender(short_token)
        if resolved not in ("masc", "femn"):
            resolved = secrets.choice(("masc", "femn"))
        # The short substitute's gender is the REAL short name's, not what
        # morphology re-reads off the fake: a feminine fake surname «уварова»
        # is also the masculine genitive the dictionary prefers, and reading it
        # back minted the grown name for a man and refused the reuse. The real
        # short canonical is unambiguous enough for the joint read.
        short_gender = morph_names.read_person(short_canonical, ())[0]
        if short_gender in ("masc", "femn") and gender in ("masc", "femn") and short_gender != gender:
            return None
        known = {w.casefold() for w in short_canonical.split()}
        # A NEW PART MAY ALREADY HAVE A SUBSTITUTE OF ITS OWN in this
        # conversation: the CRM card's `middle_name` is a lone patronymic that
        # minted before the full name arrived. Drawing the patronymic fresh
        # here would give the same real person TWO patronymics («игоревна» in
        # the card, «сергеевна» in the grown full name) and the model's
        # composition of the card's parts would no longer equal the grown token,
        # so the call leg and the result leg diverge (long_order-003). A single
        # one-word substitute for exactly this part is reused instead; two
        # people sharing the same part word stay ambiguous and fall through to
        # the random draw — merging them would be the one failure this product
        # treats as unacceptable.
        single_parts: dict[str, set[str]] = {}
        new_parts = [w for w in real_parts if w.casefold() not in known and len(w) > 2]
        if new_parts:
            # `name_parts` indexes only multi-word names, so a lone patronymic
            # the card minted is invisible there — ask `tokens` by the folded
            # canonical, which is exactly the key a single-word name is stored
            # under (case- and ё-insensitive).
            placeholders = ",".join("?" * len(new_parts))
            single_rows = self._conn.execute(
                "SELECT canonical, token FROM tokens "
                "WHERE customer=? AND entity_type='NAME' AND minted_in=? "
                f"AND canonical_fold IN ({placeholders})",
                (self._customer, self._conversation,
                 *[fold_key(w) for w in new_parts]),
            ).fetchall()
            for other, token in single_rows:
                words = [w for w in other.split() if len(w) > 2]
                if len(words) == 1 and len(token.split()) == 1:
                    single_parts.setdefault(words[0].casefold(), set()).add(token)
        names = ASSETS.get().names
        patronymics = (names.patronymics_masc if resolved == "masc" else names.patronymics_femn)
        for _ in range(12):
            built: list[str] = []
            for part, kind in zip(real_parts, shape):
                if part.casefold() in known:
                    word = _corresponding_part(part, short_canonical, short_token)
                    if word is None:
                        return None
                    built.append(word)
                else:
                    single = single_parts.get(part.casefold())
                    if single is not None and len(single) == 1:
                        built.append(next(iter(single)))
                        continue
                    if kind == "patr":
                        built.append(secrets.choice(patronymics))
                    elif kind == "surn":
                        surname = secrets.choice(ASSETS.get().fakes.last)
                        built.append(morph_names.feminine_surname(surname) if resolved == "femn" else surname)
                    elif kind == "init":
                        built.append(secrets.choice(_INITIAL_LETTERS) + ".")
                    else:
                        built.append(secrets.choice(_first_names_by_gender(ASSETS.version)[resolved]))
            candidate = " ".join(built)
            if len(set(w.casefold() for w in built)) != len(built):
                continue
            checkable = " ".join(w for w, kind in zip(built, shape) if kind != "init")
            if checkable and not morph_names.survives_round_trip(checkable, resolved):
                continue
            if not self._is_free_token(candidate, "NAME", value, canonical):
                continue
            return candidate, short_token
        return None

    def _initials_reuse(self, canonical: str, value: str) -> tuple[str, str] | None:
        """«Ващенко Т. С.» after «Ващенко Таисия Савельевна» is ONE person.

        Initials are a DERIVED form of a full name, not a second name: «Т.» and
        «С.» stand for the given name and patronymic the conversation already
        spelled out. Keyed as written, the two forms were two rows, so the model
        read one surname in the call and another in the result. The substitute
        is the same abbreviation of the full name's substitute — its surname
        word, and the first letters of its given and patronymic words — so
        «Ващенко Т. С.» becomes «Бирюкова Д. Е.» when «Ващенко Таисия
        Савельевна» became «Бирюкова Дарья Евгеньевна».

        The match is surname PLUS initials, never surname alone: «Ващенко Т. С.»
        against a conversation that holds only «Ващенко Анна Савельевна» is a
        different person, and must mint fresh — the same single-owner discipline
        as `_linked_token`, which refuses when two people share the looked-up
        word. A conversation with no full name at all also mints fresh, exactly
        as the ТЗ demands.
        """
        if not self._conversation:
            return None
        shape = morph_names.name_shape(canonical)
        real_parts = canonical.split()
        # A PURE INITIALS ABBREVIATION: a surname plus one or more initials and
        # nothing else. A mention with a full given name or patronymic is not
        # this case — it is grown (`_extends_known_person`) or reordered
        # (`_same_person_reordered`) elsewhere.
        if len(real_parts) != len(shape) or "surn" not in shape or "init" not in shape:
            return None
        if any(kind not in ("surn", "init") for kind in shape):
            return None
        surname = next(w for w, k in zip(real_parts, shape) if k == "surn")
        initials = [w.strip(".").upper() for w, k in zip(real_parts, shape) if k == "init"]
        if not initials:
            return None
        rows = self._conn.execute(
            "SELECT DISTINCT t.canonical, t.token FROM name_parts p "
            "JOIN tokens t ON t.customer = p.customer AND t.canonical = p.canonical "
            "WHERE p.customer=? AND t.entity_type='NAME' AND t.minted_in=? AND p.part=?",
            (self._customer, self._conversation, surname.casefold()),
        ).fetchall()
        candidates: list[tuple[str, str, tuple[str, ...]]] = []
        for other, token in rows:
            if other == canonical:
                continue
            other_parts = other.split()
            other_shape = morph_names.name_shape(other)
            if len(other_parts) != len(other_shape):
                continue
            other_surname = next((w for w, k in zip(other_parts, other_shape) if k == "surn"), None)
            if other_surname is None or other_surname.casefold() != surname.casefold():
                continue
            # The full name's given/patronymic words, in the written order, must
            # supply one initial each — the SAME first letters the mention spells.
            other_name_parts = [w for w, k in zip(other_parts, other_shape) if k in ("name", "patr")]
            if len(other_name_parts) != len(initials):
                continue
            if any(not w or w[0].upper() != initial
                   for w, initial in zip(other_name_parts, initials)):
                continue
            if len(token.split()) != len(other_parts):
                continue
            candidates.append((other, token, other_shape))
        if len(candidates) != 1:
            return None
        other, full_token, other_shape = candidates[0]
        token_parts = full_token.split()
        token_surname = next(w for w, k in zip(token_parts, other_shape) if k == "surn")
        token_name_parts = [w for w, k in zip(token_parts, other_shape) if k in ("name", "patr")]
        # The substitute's words, mapped by kind onto the mention's slots: the
        # surname word in the surname slot, the first letter of each given/
        # patronymic word in the matching initial slot. Counts already agree.
        name_iter = iter(token_name_parts)
        built = [token_surname if kind == "surn" else next(name_iter)[0] + "."
                 for _, kind in zip(real_parts, shape)]
        candidate = " ".join(built)
        if not self._is_free_token(candidate, "NAME", value, canonical):
            return None
        return candidate, full_token

    def _one_identity(self, tokens: set[str]) -> str | None:
        """The FULLEST of several tokens when they are one chain of `extends`
        — a short mention and the full mention grown from it — else None.
        Nesting of parts is deliberately not evidence: a random draw may by
        chance contain another person's token, and a part rule would hand a
        fragment of one person to the other. The chain exists only where this
        code built it."""
        if not tokens:
            return None
        # ONE CONNECTED COMPONENT, not one root: a short mention linked to a
        # full address is stored as a second row with the SAME token string and
        # `extends` pointing at the full one, so following parents from the
        # full token walks a cycle. Edges are undirected; the question is only
        # whether every token in the set is joined to the others by chains
        # this code built.
        rows = self._conn.execute(
            "SELECT token, extends FROM tokens WHERE customer=? AND extends IS NOT NULL "
            f"AND (token IN ({','.join('?' * len(tokens))}) "
            f"OR extends IN ({','.join('?' * len(tokens))}))",
            (self._customer, *sorted(tokens), *sorted(tokens)),
        ).fetchall()
        parent: dict[str, str] = {}

        def find(node: str) -> str:
            parent.setdefault(node, node)
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        for token, extends in rows:
            parent[find(token)] = find(extends)
        if len({find(token) for token in tokens}) != 1:
            return None
        return max(tokens, key=lambda token: (len(token.split()), len(token), token))

    def peek_token(self, value: str, entity_type: str) -> str | None:
        """Return the existing token for a value WITHOUT creating one (read-only).

        For UI highlighting: shows what a value WAS replaced with if it has been
        masked before; None if it never went through the model. Never mutates the
        vault, so rendering a dialog can't mint tokens."""
        canonical = canonicalize(entity_type, value)
        # Hold the lock around the SQLite read: the single connection is shared
        # across worker threads (check_same_thread=False), so reads must be
        # serialized with writes or sqlite3 can raise / interleave cursors.
        with self._lock:
            row = self._conn.execute(
                "SELECT token FROM tokens WHERE customer=? AND canonical=?",
                (self._customer, canonical),
            ).fetchone()
        return row[0] if row is not None else None

    def detokenize(self, token: str) -> str | None:
        """The real value, in the form a tool should receive.

        For NAME that is the CANONICAL (nominative) form, not the surface one.
        A customer writing «позвоните Иванову Петру Сергеевичу» named the person
        in the dative because the sentence required it — the person's name is
        still «Иванов Пётр Сергеевич», and that is what belongs in a CRM field.
        Returning the first-seen surface form put a declined name into the
        customer's database.

        Every other type keeps the surface form the user typed. Phones already
        behaved this way (the canonical +7… is returned), so names now follow
        the same rule rather than being the exception.
        """
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_VALUE_SQL} FROM tokens WHERE customer=? AND token=?",
                (self._customer, token),
            ).fetchone()
        return row[0] if row is not None else None

    def remember_shown(self, shown: str, original: str, entity_type: str) -> None:
        """This conversation saw `shown` where the customer wrote `original`
        (see `shown_forms`). A no-op without a conversation scope, and when
        nothing was replaced."""
        if not self._conversation or shown == original:
            return
        # The first write obtains SQLite's transaction lock before reading the
        # previous owner. A Python lock alone cannot serialize other workers.
        # A self-mapping is a sticky ambiguity marker: it preserves the visible
        # substitute instead of selecting either person's real value. It uses
        # the existing schema and expires with the conversation's other forms.
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO shown_forms "
                "(customer, conversation, shown, original, entity_type, created) VALUES (?,?,?,?,?,?)",
                (self._customer, self._conversation, shown, original, entity_type, time.time()))
            previous = self._conn.execute(
                "SELECT original, entity_type FROM shown_forms "
                "WHERE customer=? AND conversation=? AND shown=?",
                (self._customer, self._conversation, shown)).fetchone()
            if previous is None:
                raise RuntimeError("shown form disappeared inside its write transaction")
            old_original, old_type = str(previous[0]), str(previous[1])
            if (old_type == entity_type and len(original) < len(old_original)
                    and old_original.startswith(original)):
                # A TOOL'S CUT IS NOT A SECOND OWNER, AND NOT A SECOND IDENTITY.
                # The tool-result leg re-runs detection over a truncated real
                # value and re-records the substitute it renders for the cut, so
                # `raw[:85]` of a value this dialogue already named arrives here
                # as a shorter original under the same surface. Last-writer used
                # to win: the recorded original shrank to the cut, and the next,
                # longer cut was no longer a prefix of the evidence and escaped.
                # A cut whose digits also parse differently (`raw[:86]` of a
                # dictated number) was worse — the canonical keys disagreed, the
                # row became a self-mapping conflict marker, and the substitute
                # stopped restoring at all. The authoritative identity is the
                # one this dialogue recorded FIRST and fully; a strict prefix of
                # it is the same mention, shorter, and never replaces it.
                remembered: str = old_original
            else:
                old_key: str = canonicalize(entity_type, old_original)
                new_key: str = canonicalize(entity_type, original)
                if entity_type == "NAME":
                    old_key, new_key = fold_key(old_key), fold_key(new_key)
                elif entity_type == "LOC":
                    # Detection canonicalizes the normalized address. A literal
                    # homoglyph retained for rendering is not a second owner.
                    old_key = canonicalize(entity_type, normalize(old_original))
                    new_key = canonicalize(entity_type, normalize(original))
                same_value: bool = old_type == entity_type and (
                    old_original == original or (
                        old_original != shown and old_key == new_key))
                remembered = original if same_value else shown
            self._conn.execute(
                "UPDATE shown_forms SET original=?, created=? "
                "WHERE customer=? AND conversation=? AND shown=?",
                (remembered, time.time(), self._customer, self._conversation, shown))
            # Refresh active evidence before sweeping stale rows. Sweeping
            # between an ignored INSERT and its SELECT could delete this row.
            self._expire_place_parts()

    def shown_forms(self) -> list[tuple[str, str, str]]:
        """Every (shown, original, entity_type) this conversation was shown,
        longest shown form first — so that a form containing another is
        matched whole. `shown == original` marks conflicting owners; it is
        deliberately not a claim about a real value."""
        if not self._conversation:
            return []
        with self._lock:
            rows = self._conn.execute(
                "SELECT shown, original, entity_type FROM shown_forms "
                "WHERE customer=? AND conversation=? ORDER BY length(shown) DESC",
                (self._customer, self._conversation)).fetchall()
        return [(str(a), str(b), str(c)) for a, b, c in rows]

    def as_minted(self, surface: str) -> bool:
        """Every word of `surface` is a word of a NAME substitute exactly as it
        was minted — the nominative. The agent then did NOT inflect what it
        was shown, whatever the morphology prior reads into the spelling:
        a lone «Карпова» in `last_name` is the woman's nominative the card
        carried, not the masculine genitive the dictionary prefers. One
        indexed query; a word the agent bent («Карповой») is not a part."""
        words = [word.casefold() for word in surface.split() if word]
        if not words:
            return False
        asked = sorted({w for word in words for w in (word, word.replace("ё", "е"))})
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT t.part FROM token_parts AS t "
                "JOIN tokens AS k ON k.customer=t.customer AND k.token=t.token "
                f"WHERE t.customer=? AND k.entity_type='NAME' AND t.part IN ({','.join('?' * len(asked))})",
                (self._customer, *asked),
            ).fetchall()
        found = {row[0] for row in rows}
        return all(word in found or word.replace("ё", "е") in found for word in words)

    def written_form(self, canonical: str) -> str | None:
        """The surface this NAME was FIRST written in («Анне Черных» for the
        row keyed «Анна Черных»), for the restorer: when the model's form is
        syncretic between cases, the case the customer wrote in is the one
        evidence morphology does not have."""
        with self._lock:
            row = self._conn.execute(
                "SELECT original FROM tokens WHERE customer=? AND canonical=? "
                "AND entity_type='NAME'", (self._customer, canonical)).fetchone()
        return None if row is None or not row[0] else str(row[0])

    def reveal(self, token: str, for_tool: bool = False) -> tuple[str | None, str]:
        """Value and its entity type in one lookup, for the audited reveal path.

        Separate from `detokenize` because that one is the hot detokenization
        call on every model answer and has no use for the type; the access record
        does, and fetching it with a second query would double the reads on the
        one path that must not be discouraged from being audited."""
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_VALUE_SQL_BOTH} FROM tokens "
                "WHERE customer=? AND token=?",
                (self._customer, token),
            ).fetchone()
        if row is None:
            return None, ""
        return _pick_value(row[0], row[1], row[2], for_tool), row[0]

    def is_minted_token(self, value: str) -> bool:
        """True if this exact string is a token WE issued for this customer.

        Needed because a fake NAME or LOC is, by construction, a well-formed name
        or place — so detection finds it again when the model echoes it back, and
        without this guard we would mask our own substitution a second time. The
        numeric types are protected by their invalid checksums; these are not."""
        with self._lock:
            row = self._conn.execute(
                "SELECT minted_in FROM tokens WHERE customer=? AND token=? LIMIT 1",
                (self._customer, value),
            ).fetchone()
            if row is None and value.strip() and any(ch.isdigit() for ch in value):
                # A NUMERIC TOKEN IS OURS IN ANY WRITING: it is shown to the
                # model in the customer's form («8-978-272-77-64») and echoed
                # in that form or another; the digit signature is what the
                # vault indexes it by, the same way the restore leg finds it.
                digits = re.sub(r"\D", "", value)
                tail = digits[-10:] if len(digits) >= 10 else digits
                row = self._conn.execute(
                    "SELECT minted_in FROM tokens WHERE customer=? AND (digits=? OR digits10=?) "
                    "AND entity_type IN ('PHONE','SNILS','INN','CARD','PASSPORT','DOB') LIMIT 1",
                    (self._customer, digits, tail),
                ).fetchone()
        if row is None:
            return False
        # SCOPED TO THE DIALOGUE THAT MINTED IT. A substitute comes back to us
        # from the model inside the conversation it was handed to; a real person
        # who happens to bear that name walks in from another one. Without the
        # comparison the second case reads as the first and the real person goes
        # to the model unmasked — «Александр Шилов», «Владимир Наумов», measured
        # on third-party names.
        #
        # NULL is a row minted before this column existed, and an empty scope is
        # a caller that named no conversation (both entry points always name
        # one; a direct `Vault` user need not). Either way there is nothing to
        # compare, so the guard behaves as it always did rather than inventing a
        # mismatch and re-masking somebody's echo.
        minted_in = row[0]
        # THE HOST MAY HAVE DECLARED MEMORY. At customer scope the row alone
        # settles it: our substitute is ours wherever it comes back from —
        # a memory store keyed by user, a fork, another agent's session.
        # `with_pseudonym_scope` states what that costs.
        if self._pseudonym_scope == "customer":
            return True
        if not minted_in or not self._conversation:
            return True
        return minted_in == self._conversation

    def minted_tokens(self) -> tuple[str, ...]:
        """Все подмены, отчеканенные для этого клиента.

        Нужна СУДЬЕ. `surviving_substitutes` отдаёт только те, что строковый поиск ещё
        находит в ответе, — то есть уже пойманные детерминированной проверкой; а
        вопрос к модели ровно про остальные: склонённую подмену, пересказанный
        адрес, число словами. Читает и ничего не чеканит: `/spans` и `peek_token`
        держат то же правило и по той же причине.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT token FROM tokens WHERE customer=?", (self._customer,)
            ).fetchall()
        return tuple(row[0] for row in rows)

    def detokenize_many(self, tokens: set[str],
                        for_tool: bool = False) -> dict[str, str]:
        """Resolve a batch of candidate tokens in indexed point queries. Unknown
        candidates are simply absent from the result — the caller leaves that text
        untouched. This is what keeps the response leg independent of vault size."""
        return self._lookup("token", tokens, for_tool)

    def detokenize_many_typed(self, tokens: set[str],
                              for_tool: bool = False) -> dict[str, tuple[str, str]]:
        """`detokenize_many`, carrying the entity type: the restorer puts the
        value into the agent's form, and WHICH form a type has — a name's
        case, a date's notation, a number's grouping — is recorded at the
        mint, not guessed from the string."""
        return self._lookup_typed("token", tokens, for_tool)

    def resolve_digit_signatures(self, signatures: set[str],
                                 for_tool: bool = False) -> dict[str, str]:
        """Resolve numeric tokens by digit signature, for the case where the model
        reformatted one so it no longer matches its minted shape. A full-signature
        hit wins over a phone last-10 hit (the caller asks in that order)."""
        return {signature: value for signature, (_kind, value) in
                self.resolve_digit_signatures_typed(signatures, for_tool).items()}

    def resolve_digit_signatures_typed(self, signatures: set[str],
                                      for_tool: bool) -> dict[str, tuple[str, str]]:
        """Resolve the same indexed signatures while retaining the minted type.

        Rendering must not guess PHONE from an eleven-digit SNILS. Exact
        signatures retain priority over the phone last-ten alias.
        """
        tails: dict[str, tuple[str, str]] = self._lookup_typed("digits10", signatures, for_tool)
        exact: dict[str, tuple[str, str]] = self._lookup_typed("digits", signatures, for_tool)
        return {**tails, **exact}

    def resolve_name_keys_typed(self, keys: set[str], for_tool: bool = False,
                                ) -> dict[str, tuple[str, str]]:
        """Same lookup, but carrying the entity type with each value.

        The caller has to put the restored value back in the case the token was
        standing in, and WHICH inflector does that depends on what the value is.
        Guessing from the string is where «Санкт-Петербурге» became
        «Санкт-Петербургее»: the person inflector read a city as a run of name
        parts and inflected one that was already in the target case. The type is
        recorded at mint time and costs one more column in a query that already
        runs — there is no reason to infer it."""
        return self._lookup_typed("name_key", keys, for_tool)

    def _lookup_typed(self, column: str, keys: set[str], for_tool: bool = False,
                      ) -> dict[str, tuple[str, str]]:
        keys = {key for key in keys if key}
        if not keys:
            return {}
        found: dict[str, tuple[str, str]] = {}
        ordered = sorted(keys)
        for start in range(0, len(ordered), 400):
            chunk = ordered[start:start + 400]
            placeholders = ",".join("?" * len(chunk))
            with stage(f"vault.lookup.{column}"), self._lock:
                rows = self._conn.execute(
                    f"SELECT {column}, {_VALUE_SQL_BOTH}, minted_in, name_key "
                    f"FROM tokens WHERE customer=? AND {column} IN ({placeholders})",
                    (self._customer, *chunk),
                ).fetchall()
            for row in rows:
                if self._answers_another_dialogue(row[1], row[5], row[4]):
                    continue
                found[row[0]] = (row[1], _pick_value(row[1], row[2], row[3],
                                                     for_tool))
        return found

    def _answers_another_dialogue(self, entity_type: str, name_key: str | None,
                                  minted_in: str | None) -> bool:
        """A DEGENERATE PLACE KEY IS NOT UNIQUE, SO IT ANSWERS ONLY AT HOME.

        A street with no number — «наб. Ольгина», minted when the detector took
        half of «наб. Ольгина пруда, 119» — keys as «ольгин|», and every
        dialogue of that customer that is shown a fake street with the same name
        asks the same key. Dialogue B wrote «Каштановая» into a `street` field
        and the tool received dialogue A's REAL street: a disclosure, not a form
        divergence, and the same class `residual_of` closed for a piece of a
        NAME (known-issues Б23). A key that carries DIGITS names one address, so
        it stays customer-wide on purpose — «one address, one substitute, for
        ever» is what lets a corrected house keep its street.

        THE ROW DECIDES, NOT THE ROUTE TO IT. The question is asked of the
        row's own `name_key` whichever column the lookup came in by, because
        the bare street is equally reachable by its exact token — «Каштановая»
        minted with no marker IS the whole substitute — and a rule that closed
        the key and left the token open would close half a door.

        NO CONVERSATION IS NOT EVERY CONVERSATION — IT IS THE SINGLE CANDIDATE.
        A restoring leg that names none — `/unmask`, `/unmask_chunk`,
        `/unmask_arguments` without `conversation_id`, where there is no
        transcript to derive one from — stands in no dialogue, so it cannot
        claim to be the one that minted this row. Reading it anyway is how one
        dialogue's real street reached another's tool (Б28). Refusing it
        outright is not the answer either: the documented sidecar client
        (`docs/integration-diva-backend-api.md`) sends no `conversation_id` at
        all, and a silent no would break a working integration. So such a leg
        gets the answer only when the customer has exactly ONE fake street by
        this name (`_sole_place_owner`) — the same single-candidate rule the
        conversation scope itself is built on, applied one level wider.

        A host that wants the wide answer regardless says so — by naming the
        conversation, or by declaring agent memory (`with_pseudonym_scope`),
        exactly as `is_minted_token` takes the same declaration.

        The price is the trade `#conversation-scope` already records: a bare
        street named in one dialogue and asked about in another no longer
        resolves and comes back as a residual token, VISIBLY
        (`place_fragment_is_ours` → `redact.surviving_substitutes`), instead of
        answering with somebody else's street silently."""
        if entity_type != "LOC" or not name_key:
            return False
        if self._pseudonym_scope == "customer":
            return False
        if any(character.isdigit() for character in name_key):
            return False
        if not minted_in:
            # Строка тома, записанного до появления столбца: сравнивать не с чем,
            # и правило её не касается ни в одном режиме.
            return False
        if self._conversation:
            return minted_in != self._conversation
        return not self._sole_place_owner(name_key)

    def resolve_name_keys(self, keys: set[str]) -> dict[str, str]:
        """Resolve NAME tokens the model INFLECTED, by case-invariant key.

        The second line of defence, and the reason a fake no longer reaches a
        customer's tool when the model writes `Руслану Хвостову` instead of the
        nominative it was handed. Phones have had this since the digit-signature
        reindex; names went without it, which is precisely where the silent
        failure lived.
        """
        return self._lookup("name_key", keys)

    def _lookup(self, column: str, keys: set[str],
                for_tool: bool = False) -> dict[str, str]:
        """Point-query `keys` against an indexed column. `column` is chosen from
        this module's own literals, never from caller input, so interpolating it
        into the statement cannot carry injection."""
        keys = {key for key in keys if key}
        if not keys:
            return {}
        found: dict[str, str] = {}
        ordered = sorted(keys)
        stage_name = f"vault.lookup.{column}"
        # SQLite caps host parameters per statement; chunk so a long answer with
        # many candidates can never exceed it.
        for start in range(0, len(ordered), 400):
            chunk = ordered[start:start + 400]
            placeholders = ",".join("?" * len(chunk))
            with stage(stage_name), self._lock:
                rows = self._conn.execute(
                    f"SELECT {column}, {_VALUE_SQL_BOTH} FROM tokens "
                    f"WHERE customer=? AND {column} IN ({placeholders})",
                    (self._customer, *chunk),
                ).fetchall()
            found.update({row[0]: _pick_value(row[1], row[2], row[3], for_tool)
                          for row in rows})
        return found
