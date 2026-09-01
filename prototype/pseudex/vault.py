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

from pseudex import morph_names, morph_places
from pseudex.spoken import numeral_runs, run_to_digits
from pseudex.profiling import stage
from pseudex.ru_pii import validate_inn, validate_luhn, validate_ogrn, validate_snils
from pseudex.sqlite_setup import (
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

# Tokens must be UNIQUE per customer, so these pools bound how many distinct
# people and places one org can ever have. They used to be flat lists of five,
# which meant the sixth distinct person spun `tokenize` forever looking for a
# free token — an unbounded hang on the request path, hit by any real customer
# on day one. Names are now COMBINATORIAL (first x last), which is what makes the
# space large enough to stop being a limit.
#
# INVARIANT: every fake first name must be one our OWN detector recognises.
# Unusual names (Аглая, Ясна) were tried and broke the re-masking guard: the
# gazetteer did not know them, so detection split `Аглая Котов` and only found
# the surname — which is not a minted token, so it was masked a second time and
# the identity drifted. test_product.py::test_fake_names_are_self_recognised
# pins this.
_FAKE_FIRST = [
    "Александр", "Алексей", "Андрей", "Антон", "Артур", "Борис", "Вадим",
    "Валерий", "Василий", "Виктор", "Владимир", "Глеб", "Григорий", "Даниил",
    "Денис", "Дмитрий", "Евгений", "Егор", "Иван", "Игорь", "Илья", "Кирилл",
    "Константин", "Леонид", "Максим", "Марк", "Михаил", "Никита", "Николай",
    "Олег", "Павел", "Роман", "Руслан", "Сергей", "Степан", "Тимофей", "Юрий",
    "Александра", "Алина", "Анастасия", "Анна", "Валентина", "Вера", "Виктория",
    "Галина", "Дарья", "Екатерина", "Елена", "Ирина", "Карина", "Кристина",
    "Ксения", "Лариса", "Маргарита", "Марина", "Мария", "Надежда", "Нина",
    "Оксана", "Ольга", "Полина", "Светлана", "София", "Татьяна", "Юлия",
    # WIDENED because the substitute now mirrors the original's SHAPE. A name
    # written as one word is replaced by one word, so a customer with many
    # single-name contacts — «меня зовут Аня» is how a chat says it — draws from
    # this pool alone. At 65 entries `_unique_token` exhausted and the gateway
    # started returning 5xx; the two-part shape it used to force had 1820
    # combinations and hid the limit.
    #
    # Still a literal list rather than the leased 28k dictionary, because
    # TOKEN_RE anchors NAME on exactly these words: a token has to be findable
    # in the model's reply, and "any capitalised word" is not a pattern that can
    # do that safely.
    "Аркадий", "Артём", "Богдан", "Валентин", "Вениамин", "Виталий", "Владислав",
    "Всеволод", "Вячеслав", "Геннадий", "Георгий", "Герман", "Гордей", "Демьян",
    "Захар", "Игнат", "Кузьма", "Лев", "Макар", "Матвей", "Мирон", "Мирослав",
    "Назар", "Остап", "Пётр", "Платон", "Прохор", "Радислав", "Ратмир", "Родион",
    "Савва", "Савелий", "Святослав", "Семён", "Тарас", "Тимур", "Трофим", "Фёдор",
    "Филипп", "Харитон", "Эдуард", "Эмиль", "Яков", "Ян", "Ярослав",
    "Агата", "Аглая", "Алевтина", "Алиса", "Алла", "Альбина", "Амелия", "Ангелина",
    "Антонина", "Арина", "Белла", "Богдана", "Валерия", "Варвара", "Василиса",
    "Вероника", "Влада", "Власта", "Гелена", "Диана", "Дина", "Ева", "Евгения",
    "Елизавета", "Жанна", "Зинаида", "Злата", "Зоя", "Иванна", "Инга", "Инна",
    "Иоланта", "Капитолина", "Клавдия", "Лада", "Лидия", "Лилия", "Любовь",
    "Людмила", "Майя", "Милана", "Милена", "Мирослава", "Наталья", "Нелли",
    "Николь", "Олеся", "Прасковья", "Раиса", "Регина", "Римма", "Роза", "Руслана",
    "Сабина", "Серафима", "Снежана", "Стелла", "Таисия", "Тамара", "Ульяна",
    "Фаина", "Христина", "Эвелина", "Эльвира", "Эмилия", "Ярослава",
]
_FAKE_LAST = [
    "Лебедев", "Жуков", "Тихонов", "Котов", "Сорокин", "Беляев", "Гущин",
    "Ершов", "Зимин", "Карпов", "Лужин", "Мещеряков", "Наумов", "Осипов",
    "Панов", "Рыбаков", "Сазонов", "Тарасов", "Устинов", "Фомин", "Хвостов",
    "Цветков", "Чижов", "Шилов", "Щукин", "Юдин", "Яровой", "Бирюков",
]
# A WOMAN MENTIONED BY SURNAME ALONE CANNOT BE GIVEN ANY NAME ABOVE. Every one
# ends in -ов/-ин, whose feminine form is syncretic: «Лебедева» is the woman's
# nominative and the man's genitive, so its cases do not reduce to one key and
# `survives_round_trip` rejects it — correctly, because a token that stops
# resolving hands the fake to the customer's tool.
#
# Not one of the 28 passed, which is a category and not a near miss: there was
# NO one-word substitute for a lone feminine surname, so «фамилия Иванова» fell
# back to the two-word shape and the model was handed «фамилия Диана Сорокина»
# — a construction it repairs, and a repaired token is the failure the fallback
# exists to avoid.
#
# These do not inflect for gender at all, so the feminine form IS the masculine
# one and has one key in every case. All are ordinary surnames carried by
# Russian citizens — Ukrainian, Armenian, Georgian, and the native -ых/-их.
#
# A SEPARATE LIST, not more entries above, because they answer a different
# question. Folded into the general pool they would be half of every customer's
# fake population, and a Russian company reading its own masked traffic would
# see a product that does not know the country it is sold in.
#
# THE SIZE IS THE POINT. Six of them meant the SEVENTH woman a customer ever
# named by surname alone could not be minted at all — a permanent fail-closed
# 5xx for that customer, the same defect the address pool had at 33.
_FAKE_LAST_INVARIANT = [
    "Шевчук", "Ткачук", "Бондарчук", "Кравчук", "Гончарук", "Ковальчук",
    "Павлюк", "Савчук", "Марчук", "Данилюк",
    "Саркисян", "Аванесян", "Петросян", "Акопян", "Григорян", "Арутюнян",
    "Бабаян", "Казарян", "Хачатрян", "Мкртчян",
    "Петренко", "Коваленко", "Савченко", "Бондаренко", "Кравченко", "Ткаченко",
    "Черных", "Белых", "Седых", "Долгих", "Рыжих",
    "Гвелесиани", "Церетели", "Бойко", "Головко",
]
# LOC IS COMBINATORIAL, and it has to be. A flat list of 33 places meant the
# 34th distinct address an organisation ever sent could not be minted:
# `_unique_token` burned its attempts on collisions and raised, so a fail-closed
# 5xx on every message containing a new address, permanently, for that customer.
# Any delivery or logistics client crosses 33 addresses on day one — this was the
# same defect as the old five-name pool, still live on the type most exposed to
# it.
#
# Streets carry a house number, which is what makes the space large; cities stay
# bare because "Суздале, 47" is not a city. Both remain literal enough for
# TOKEN_RE to match precisely — a generic "capitalised Cyrillic word" there would
# make every ordinary word in a reply a detokenization candidate.
# STORED IN THE NOMINATIVE, which is a reversal. They used to be prepositional
# («Зеленограде») because they were written to slot into «в …», and every use
# derived the nominative back — which is guesswork for a place name: pymorphy3
# reads «Белёва» as nominative with a higher score than genitive, so the derived
# form came out «Белёва» and the customer saw a city that does not exist.
#
# Deriving the OBLIQUE from the nominative is the safe direction — that is what
# `morph_places.inflect_place` is for — and it also fixes a quieter problem:
# TOKEN_RE matches these literally for detokenization, and it was matching forms
# we had already stopped emitting.
_FAKE_CITIES = [
    "Зеленоград", "Светлогорск", "Приозерск", "Гатчина", "Кинешма",
    "Торжок", "Валдай", "Бологое", "Кимры", "Сортавала", "Луга", "Тихвин",
    "Мышкин", "Углич", "Плёс", "Суздаль", "Елец", "Задонск", "Данков",
    "Венёв", "Алексин", "Белёв", "Крапивна", "Одоев", "Чернь",
]
_FAKE_STREETS = [
    "Берёзовой", "Кленовой", "Ольховой", "Рябиновой", "Вязовой", "Тополиной",
    "Липовой", "Ясеневой", "Сосновой", "Еловой", "Кедровой", "Пихтовой",
    "Ивовой", "Вишнёвой", "Грушевой", "Абрикосовой", "Каштановой", "Буковой",
    "Осиновой", "Черёмуховой", "Барбарисовой", "Жасминовой", "Сиреневой",
    "Лавандовой", "Мятной", "Полевой", "Луговой", "Озёрной", "Речной",
    "Родниковой",
]
# 30 streets x 199 numbers + 25 cities = 5995 distinct LOC tokens per customer.
_FAKE_HOUSE_MAX = 199
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
    if entity_type == "EMAIL":
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
        return (value.strip().upper()
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
    for _ in range(50):
        body = _rand_digits(9)
        candidate = f"{body[:3]}-{body[3:6]}-{body[6:9]} {_rand_digits(2)}"
        if not validate_snils(candidate):
            return candidate
    raise RuntimeError("could not generate a checksum-INVALID СНИЛС")


def _fake_inn() -> str:
    for _ in range(50):
        candidate = _rand_digits(10)
        if not validate_inn(candidate):
            return candidate
    raise RuntimeError("could not generate a checksum-INVALID ИНН")


def _fake_card() -> str:
    for _ in range(50):
        body = "4" + _rand_digits(15)
        if not validate_luhn(body):
            return f"{body[:4]} {body[4:8]} {body[8:12]} {body[12:]}"
    # Returning `body` here used to emit an UNFORMATTED 16-digit string, which
    # TOKEN_RE does not match — an unreversible token, silently.
    raise RuntimeError("could not generate a Luhn-INVALID card number")


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


def name_key(token: str) -> str:
    """Case-invariant signature of a personal name: its nominative, lowercased.

    `Руслану Хвостову`, `Руслана Хвостова` and `Руслан Хвостов` all reduce to
    one key, so a token the model inflected still resolves to the real value.
    """
    return morph_names.to_nominative(token).lower()


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


def _digit_signatures(token: str, entity_type: str) -> tuple[str | None, str | None]:
    """Digit signature of a NUMERIC token, so a token the model reformatted
    (separators stripped, +7 rewritten as 8) still resolves. Phones also key on
    their last 10 digits because the country code varies. Non-numeric types get
    NULL so they stay out of the signature indexes."""
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
_DATE_PARTS = re.compile(r"(?:^|\D)(\d{1,4})[.\-/](\d{1,2})[.\-/](\d{1,4})(?:\D|$)")


def _is_future(original: str) -> bool:
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
    if _is_future(original):
        # Future: near enough to read as a real booking, never today itself, so
        # the substitute cannot be mistaken for «сегодня» by a model reasoning
        # about relative dates.
        year = year_now + secrets.randbelow(3) + 1
    else:
        year = 1960 + secrets.randbelow(max(1, year_now - 1960))
    return (f"{secrets.randbelow(28) + 1:02d}."
            f"{secrets.randbelow(12) + 1:02d}.{year}")


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


@functools.lru_cache(maxsize=1)
def _first_names_by_gender() -> dict[str, tuple[str, ...]]:
    """Split the leased first-name pool by gender, ONCE, using morphology.

    Derived rather than shipped as two lists: the pool is leased data and the
    split is an algorithm, so this keeps the bundle unchanged. Names morphology
    cannot classify fall back to the -а/-я ending, which is reliable for Russian
    GIVEN names (the masculine exceptions — Никита, Илья, Фома, Кузьма — are all
    in the dictionary and never reach the fallback).
    """
    buckets: dict[str, list[str]] = {"masc": [], "femn": []}
    for name in _FAKE_FIRST:
        gender = morph_names.given_name_gender(name)
        buckets[gender or ("femn" if name.endswith(("а", "я")) else "masc")].append(name)
    return {"masc": tuple(buckets["masc"]), "femn": tuple(buckets["femn"])}


def _fake_city(original: str) -> str:
    """A city of the same GENDER as the one it replaces.

    Gender is not cosmetic here, it decides whether the case can be read back.
    Russian feminine place names collapse in the oblique cases — «Сортавале» is
    dative, prepositional and genitive at once — so a masculine city replaced by
    a feminine one leaves the restorer guessing, and «Санкт-Петербурге» came back
    «Санкт-Петербурга». The same rule that makes a fake NAME agree with the real
    person's gender applies to places, for the same reason.
    """
    wanted = morph_places.place_gender(original) if original else None
    pool = [city for city in _FAKE_CITIES
            if morph_places.place_gender(city) == wanted] if wanted else []
    return secrets.choice(pool or _FAKE_CITIES)


@functools.lru_cache(maxsize=1)
def _usable_streets() -> tuple[str, ...]:
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
    for raw in _FAKE_STREETS:
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
            "fail-closed 5xx — widen _FAKE_STREETS")
    return tuple(usable)


def _fake_place(original: str) -> str:
    """A place of the SAME KIND as the one it replaces, in the nominative.

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
    street = morph_places.to_nominative(secrets.choice(_usable_streets()))
    # The pool is written feminine because most generics are; reusing the
    # original's generic word means the name has to follow it.
    street = morph_places.agree_with_generic(street, gender)
    # Marker order follows the generic: a full word leads («улица Тополиная»),
    # an abbreviation leads with a dot («ул. Тополиная»), and «проспект» reads
    # naturally after the name («Тополиный проспект»).
    full = morph_places.generic_full(generic)
    abbreviated = generic.lower() != full
    if abbreviated:
        # An abbreviation always leads, and keeps the exact form written: «пр-т»
        # stays «пр-т», never «проспект» and never «пр-т.» — the hyphenated forms
        # take no trailing dot.
        head = f"{generic}{'' if '-' in generic else '.'} {street}"
    elif full in ("проспект", "бульвар"):
        head = f"{street} {generic}"
    else:
        head = f"{generic} {street}"

    out = head
    if shape.get("has_city"):
        out = f"{_fake_city(original)}, {out}"
    if shape.get("has_house", True):
        # NO COMMA before the house number. With one, `_merge_places` stops at
        # the house and the flat is left outside the span — so the token we mint
        # is not the token detection returns, the re-masking guard does not
        # recognise it, and our own substitute gets masked a second time.
        # «улица Рябиновая 83, кв. 203» is detected whole; the comma version is
        # not, and it is also how people actually write it.
        out = f"{out} {secrets.randbelow(_FAKE_HOUSE_MAX) + 1}"
    if shape.get("has_flat"):
        out = f"{out}, кв. {secrets.randbelow(250) + 1}"
    return out


_INITIAL_LETTERS = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЭЮЯ"


@functools.lru_cache(maxsize=1)
def _invariant_last_names() -> tuple[str, ...]:
    """The surnames whose feminine form resolves in every case.

    Asked of morphology rather than listed, so adding a name to `_FAKE_LAST`
    cannot leave a stale second list behind. Empty would mean the pool has
    drifted to nothing usable, and a caller silently falling back to two words
    is how that stayed invisible before — so it is stated here instead.
    """
    usable = tuple(surname for surname in _FAKE_LAST + _FAKE_LAST_INVARIANT
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
            "that would get a fail-closed 5xx — widen _FAKE_LAST_INVARIANT")
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
        pool = _first_names_by_gender()[resolved]
        # A LONE FEMININE SURNAME HAS ONLY ONE WORKABLE POOL. Any -ова/-ина form
        # is syncretic and fails its own round trip, so drawing from the whole
        # list and hoping is not a strategy — it is 12 retries that usually work
        # and sometimes silently produce a two-word name instead. The subset is
        # DERIVED, not a second list, so it cannot drift out of step with the
        # first (the same reason `feminine_surname` derives rather than stores).
        surnames = (_invariant_last_names()
                    if plan == ("surn",) and resolved == "femn" else _FAKE_LAST)
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
    real_shape = morph_names.name_shape(full_canonical)
    fake_shape = morph_names.name_shape(full_token)
    real_parts = full_canonical.split()
    fake_parts = full_token.split()
    if len(real_shape) != len(real_parts) or len(fake_shape) != len(fake_parts):
        return None
    lowered = mention.casefold()
    for index, part in enumerate(real_parts):
        if part.casefold() != lowered:
            continue
        kind = real_shape[index]
        for fake_index, fake_kind in enumerate(fake_shape):
            if fake_kind == kind:
                return fake_parts[fake_index]
        return None
    return None


def _render_token(entity_type: str, gender: str | None = None,
                  original: str = "") -> str:
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
        return _fake_inn()
    if entity_type == "CARD":
        return _fake_card()
    if entity_type == "PASSPORT":
        return f"{_rand_digits(2)} {_rand_digits(2)} {_rand_digits(6)}"
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
        return _fake_place(original)
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
            rf"|(?i:{abbrs})\.?\s{name})")         # ул. Тополиная
    # Cities inflect too — «Сортавала» is written «Сортавалу» after «в». The
    # nominative literal matched neither, so the city-prefixed alternative never
    # fired, the head-only one did, and its key (no city) missed the stored key
    # (with city). Same stem treatment as the generics; the mandatory «, » that
    # follows a city in a minted token is what keeps a short stem from running
    # into an unrelated word.
    city = "|".join(_city_stem(value) + r"\w{0,2}" for value in _FAKE_CITIES)
    # The house number is written without a comma now, but tokens minted
    # BEFORE that change are in customers' vaults and still have to be
    # recognised in a reply — so both separators are accepted.
    return rf"(?:(?:{city}), )?{head}(?:,? \d{{1,3}})?(?:,? кв\.? ?\d{{1,3}})?"


LOC_TOKEN_PATTERN = _loc_token_pattern()

TOKEN_RE = re.compile("|".join([
    r"[a-z]{8}@example\.ru",                      # EMAIL
    # NAME is combinatorial, so it is anchored on the FIRST-NAME pool rather than
    # listed exhaustively or matched as "two capitalised words". The generic
    # shape was tried and is wrong: scanning left to right, `Клиент Мирослава
    # Фомин` matches `Клиент Мирослава` first and the real token is never seen —
    # an unresolvable token reaching a tool, the exact failure this pattern
    # exists to prevent. Anchoring on a distinctive given name cannot drift that
    # way, and over-matching a real person with the same given name is harmless:
    # the candidate simply fails the vault lookup.
    r"\b(?:" + "|".join(_FAKE_FIRST) + r") [А-ЯЁ][а-яё]+",   # NAME
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
    *(rf"\b{re.escape(value)}\b" for value in _FAKE_CITIES),       # LOC (city)
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
    r"[АВЕКМНОРСТУХABCEHKMNOPRSTUVXY]\d{3}[АВЕКМНОРСТУХABCEHKMNOPRSTUVXY]{2}\d{2,3}",  # PLATE
    r"\d{4} \d{4} \d{4} \d{4}",                   # CARD
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
    r"\+79\d{9}",                                 # PHONE
    r"REDACTED[0-9a-f]{6}",                       # fallback
    r"\b\d{10}\b",                                # INN — least specific, last
]))


class Vault:
    """Persistent per-customer token store (external state -> class)."""

    def __init__(self, db_path: str, customer_id: str) -> None:
        self._customer = customer_id
        # THE CONVERSATION THIS VIEW IS SCOPED TO, empty when there is none.
        # Not a constructor argument: the Vault is built once per org and cached,
        # while a conversation lives for one request. `for_conversation` hands
        # out a view instead — see there for why the scope has to exist at all.
        self._conversation = ""
        self._lock = threading.Lock()
        self._conn = sqlite_connect(db_path, VAULT_STORE)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tokens ("
            "customer TEXT, canonical TEXT, entity_type TEXT, token TEXT, "
            "PRIMARY KEY (customer, canonical))"
        )
        # Which words each NAME row is made of, so a later partial mention can
        # find its person by an indexed point query instead of a table scan.
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS name_parts ("
            "customer TEXT, part TEXT, canonical TEXT, "
            "PRIMARY KEY (customer, part, canonical))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_name_parts ON name_parts (customer, part)"

        )
        self._conn.execute(
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
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_token_parts ON token_parts (customer, part)"
        )
        self._conn.execute(
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
            "PRIMARY KEY (customer, conversation, part, canonical))"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_place_parts "
            "ON place_parts (customer, conversation, part)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_place_parts_created "
            "ON place_parts (created)"
        )
        self._migrate_digit_signatures()
        self._migrate_name_keys()
        self._migrate_original_form()
        self._migrate_first_seen()
        self._migrate_place_created()
        self._migrate_fold_key()
        self._migrate_minted_in()
        # Every lookup on the response leg is an indexed point query, so
        # detokenization cost tracks the length of the answer, not the size of
        # the vault. Without these indexes each one degrades to a table scan.
        for statement in (
            "CREATE INDEX IF NOT EXISTS idx_tokens_token ON tokens (customer, token)",
            "CREATE INDEX IF NOT EXISTS idx_tokens_digits ON tokens (customer, digits)",
            "CREATE INDEX IF NOT EXISTS idx_tokens_digits10 ON tokens (customer, digits10)",
            "CREATE INDEX IF NOT EXISTS idx_tokens_namekey ON tokens (customer, name_key)",
        ):
            self._conn.execute(statement)
        self._conn.commit()

    def _migrate_name_keys(self) -> None:
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
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(tokens)")}
        if "name_key" in columns:
            return
        self._conn.execute("ALTER TABLE tokens ADD COLUMN name_key TEXT")
        rows = self._conn.execute(
            "SELECT customer, canonical, token FROM tokens WHERE entity_type='NAME'"
        ).fetchall()
        for customer, canonical, token in rows:
            self._conn.execute(
                "UPDATE tokens SET name_key=? WHERE customer=? AND canonical=?",
                (name_key(token), customer, canonical),
            )
        self._conn.commit()

    def _migrate_original_form(self) -> None:
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
        columns = [row[1] for row in self._conn.execute("PRAGMA table_info(tokens)").fetchall()]
        if "original" in columns:
            return
        self._conn.execute("ALTER TABLE tokens ADD COLUMN original TEXT")
        self._conn.execute("UPDATE tokens SET original = canonical WHERE original IS NULL")

    def _migrate_digit_signatures(self) -> None:
        """Add + backfill the digit-signature columns used to resolve a numeric
        token the model REFORMATTED. Previously this index was rebuilt from every
        row of the vault on every single response; storing the signature makes it
        an indexed lookup instead."""
        columns = [row[1] for row in self._conn.execute("PRAGMA table_info(tokens)").fetchall()]
        if "digits" in columns:
            return
        self._conn.execute("ALTER TABLE tokens ADD COLUMN digits TEXT")
        self._conn.execute("ALTER TABLE tokens ADD COLUMN digits10 TEXT")
        rows = self._conn.execute(
            "SELECT customer, canonical, token, entity_type FROM tokens"
        ).fetchall()
        for customer, canonical, token, entity_type in rows:
            digits, digits10 = _digit_signatures(token, entity_type)
            self._conn.execute(
                "UPDATE tokens SET digits=?, digits10=? WHERE customer=? AND canonical=?",
                (digits, digits10, customer, canonical),
            )

    def _unique_token(self, entity_type: str, gender: str | None = None,
                      original: str = "", canonical: str = "") -> str:
        """Mint a token not already used for this customer.

        BOUNDED on purpose. This used to loop until it found a free token, which
        turned an exhausted pool into an unbounded hang on the request path — the
        flat five-name list meant the sixth distinct person in an org spun here
        forever. The pool is combinatorial now, but a bound still belongs here: a
        loud failure is recoverable, a hung request is not, and in a fail-closed
        gateway the 5xx is the correct outcome."""
        for attempt in range(_TOKEN_MINT_ATTEMPTS):
            token = _render_token(entity_type, gender, original)
            # The settlement pool is a flat 25 names with no combinatorial
            # dimension, so a customer past 25 distinct cities would exhaust it
            # and get a fail-closed 5xx on every message with a new one. Falling
            # back to the street shape is a mismatch in a rare case; a permanent
            # 5xx is an outage. Attempts are bounded either way.
            if entity_type == "LOC" and attempt >= _TOKEN_MINT_ATTEMPTS // 2:
                street = morph_places.to_nominative(secrets.choice(_usable_streets()))
                token = f"улица {street}, {secrets.randbelow(_FAKE_HOUSE_MAX) + 1}"
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
            if entity_type == "NAME" and original and _shares_a_word(token, original):
                continue
            # THE ROW BEING MINTED IS NOT IN THE TABLE YET, so the lookup below
            # cannot see it and a substitute is free to come out equal to the
            # very value it replaces. Measured: «15.06.1963» minted as
            # «15.06.1963» — a date of birth «masked» into itself, indexed as a
            # token, and thereafter skipped by the re-masking guard for every
            # other person who shares it. The pools are large enough that this is
            # rare and small enough that it happens.
            if token == canonical or (original and token == original):
                continue
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
                return token
        raise RuntimeError(
            f"exhausted the {entity_type} token pool for customer "
            f"{self._customer!r} after {_TOKEN_MINT_ATTEMPTS} attempts — widen "
            f"the pool in _render_token"
        )

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

    def tokenize(self, value: str, entity_type: str) -> str:
        with stage("vault.tokenize"):
            return self._tokenize(value, entity_type)

    def _tokenize(self, value: str, entity_type: str) -> str:
        canonical = canonicalize(entity_type, value)
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
            gender = (morph_names.detect_gender(value)
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
            token = self._linked_token(canonical, value) if entity_type == "NAME" else None
            linked_place = (self._linked_place(canonical, value)
                            if entity_type == "LOC" else None)
            if linked_place is not None:
                token, canonical = linked_place, scoped
            if token is None:
                token = self._unique_token(entity_type, gender, value, canonical)
            digits, digits10 = _digit_signatures(token, entity_type)
            # `value` (not `canonical`) — the surface form the user actually
            # typed, which is what the tool must receive. First writer wins: the
            # same person written two ways keeps the form seen first, so what the
            # tool gets is stable across turns instead of flipping with phrasing.
            try:
                self._conn.execute(
                    "INSERT INTO tokens "
                    "(customer, canonical, entity_type, token, digits, digits10, "
                    "original, first_seen, name_key, canonical_fold, minted_in) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (self._customer, canonical, entity_type, token, digits, digits10,
                     value, time.time(),
                     name_key(token) if entity_type == "NAME"
                     else place_key(token) if entity_type == "LOC" else None,
                     fold_key(canonical) if entity_type == "NAME" else None,
                     self._conversation),
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
            if (entity_type == "LOC" and self._conversation
                    and morph_places.place_shape(value).get("has_city")):
                part = morph_places.street_house_key(value)
                if part:
                    self._conn.execute(
                        "INSERT OR IGNORE INTO place_parts "
                        "(customer, conversation, part, canonical, created) "
                        "VALUES (?,?,?,?,?)",
                        (self._customer, self._conversation, part, canonical,
                         time.time()))
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
                fake_parts = {word.casefold() for word in token.split()
                              if len(word) > 2}
            elif entity_type == "LOC":
                stems, numbers = morph_places.signature_parts(token)
                fake_parts = set(stems) | set(numbers)
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

    def place_owner(self, candidate: str) -> str | None:
        """Адресная подмена, ЧАСТЬЮ которой является этот фрагмент.

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
        parts = [*stems, *numbers]
        if not parts:
            return None
        with self._lock:
            owners: list[set[str]] = []
            for part in parts:
                rows = self._conn.execute(
                    "SELECT t.token FROM token_parts AS t "
                    "JOIN tokens AS k ON k.customer=t.customer AND k.token=t.token "
                    "WHERE t.customer=? AND t.part=? AND k.entity_type='LOC'",
                    (self._customer, part),
                ).fetchall()
                if not rows:
                    return None
                owners.append({row[0] for row in rows})
        common = set.intersection(*owners)
        return next(iter(common)) if len(common) == 1 else None

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
        words = [word.casefold() for word in candidate.split() if len(word) > 2]
        if not words:
            return None
        with self._lock:
            owners: list[set[str]] = []
            for word in words:
                rows = self._conn.execute(
                    "SELECT token FROM token_parts WHERE customer=? AND part=?",
                    (self._customer, word),
                ).fetchall()
                if not rows:
                    return None
                owners.append({row[0] for row in rows})
        shared = set.intersection(*owners)
        return next(iter(shared)) if len(shared) == 1 else None

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

    def _linked_place(self, canonical: str, value: str) -> str | None:
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
        if morph_places.place_shape(value).get("has_city"):
            return None
        rows = self._conn.execute(
            "SELECT t.token FROM place_parts p "
            "JOIN tokens t ON t.customer = p.customer AND t.canonical = p.canonical "
            "WHERE p.customer=? AND p.conversation=? AND p.part=? "
            "AND t.entity_type='LOC' LIMIT 2",
            (self._customer, self._conversation, part),
        ).fetchall()
        if len(rows) != 1:
            return None
        derived = morph_places.strip_leading_city(rows[0][0])
        if not morph_places.place_shape(value).get("has_flat"):
            derived = morph_places.strip_flat(derived)
        # A projection identical to the full token is not a projection: the
        # stored address had no city either, so there is nothing shorter to
        # render and the two mentions are the same string anyway.
        return derived or None

    def _linked_token(self, canonical: str, surface: str) -> str | None:
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
            return derived
        return None

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
                "SELECT CASE WHEN entity_type='NAME' THEN canonical ELSE original END FROM tokens WHERE customer=? AND token=?",
                (self._customer, token),
            ).fetchone()
        return row[0] if row is not None else None


    def _migrate_place_created(self) -> None:
        """Add the sweep timestamp to a `place_parts` table written before it.

        The table itself is new, but a developer volume from earlier today has
        rows without the column, and without it the sweep would raise on every
        insert — turning a housekeeping detail into a fail-closed 5xx on every
        message carrying an address.
        """
        columns = [row[1] for row in
                   self._conn.execute("PRAGMA table_info(place_parts)").fetchall()]
        if "created" in columns:
            return
        self._conn.execute(
            "ALTER TABLE place_parts ADD COLUMN created REAL NOT NULL DEFAULT 0")
        self._conn.execute("UPDATE place_parts SET created=? WHERE created=0",
                           (time.time(),))
        self._conn.commit()

    def _migrate_first_seen(self) -> None:
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
                   self._conn.execute("PRAGMA table_info(tokens)").fetchall()]
        if "first_seen" in columns:
            return
        self._conn.execute("ALTER TABLE tokens ADD COLUMN first_seen REAL")
        self._conn.execute("UPDATE tokens SET first_seen=? WHERE first_seen IS NULL",
                           (time.time(),))
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tokens_first_seen ON tokens (first_seen)")
        self._conn.commit()

    def _migrate_fold_key(self) -> None:
        """Add the case/ё-insensitive lookup signature to existing vaults.

        Backfilled in place: a customer's rows are their people, and rekeying
        them would be a rewrite of the thing the product exists to keep stable.
        The column is additive and the exact-canonical lookup still runs first,
        so a vault that has not been migrated yet behaves exactly as before.
        """
        columns = [row[1] for row in
                   self._conn.execute("PRAGMA table_info(tokens)").fetchall()]
        if "canonical_fold" in columns:
            return
        self._conn.execute("ALTER TABLE tokens ADD COLUMN canonical_fold TEXT")
        rows = self._conn.execute(
            "SELECT customer, canonical FROM tokens").fetchall()
        self._conn.executemany(
            "UPDATE tokens SET canonical_fold=? WHERE customer=? AND canonical=?",
            [(fold_key(canonical), customer, canonical) for customer, canonical in rows])
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tokens_fold "
            "ON tokens (customer, canonical_fold)")
        self._conn.commit()

    def _migrate_minted_in(self) -> None:
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
                   self._conn.execute("PRAGMA table_info(tokens)").fetchall()]
        if "minted_in" not in columns:
            self._conn.execute("ALTER TABLE tokens ADD COLUMN minted_in TEXT")
            self._conn.commit()

    def reveal(self, token: str) -> tuple[str | None, str]:
        """Value and its entity type in one lookup, for the audited reveal path.

        Separate from `detokenize` because that one is the hot detokenization
        call on every model answer and has no use for the type; the access record
        does, and fetching it with a second query would double the reads on the
        one path that must not be discouraged from being audited."""
        with self._lock:
            row = self._conn.execute(
                "SELECT CASE WHEN entity_type='NAME' THEN canonical ELSE original END, entity_type FROM tokens WHERE customer=? AND token=?",
                (self._customer, token),
            ).fetchone()
        return (row[0], row[1]) if row is not None else (None, "")

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
        if not minted_in or not self._conversation:
            return True
        return minted_in == self._conversation

    def minted_tokens(self) -> tuple[str, ...]:
        """Все подмены, отчеканенные для этого клиента.

        Нужна СУДЬЕ. `residual_tokens` отдаёт только те, что строковый поиск ещё
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

    def detokenize_many(self, tokens: set[str]) -> dict[str, str]:
        """Resolve a batch of candidate tokens in indexed point queries. Unknown
        candidates are simply absent from the result — the caller leaves that text
        untouched. This is what keeps the response leg independent of vault size."""
        return self._lookup("token", tokens)

    def resolve_digit_signatures(self, signatures: set[str]) -> dict[str, str]:
        """Resolve numeric tokens by digit signature, for the case where the model
        reformatted one so it no longer matches its minted shape. A full-signature
        hit wins over a phone last-10 hit (the caller asks in that order)."""
        resolved = self._lookup("digits10", signatures)
        resolved.update(self._lookup("digits", signatures))  # exact wins over tail
        return resolved

    def resolve_name_keys_typed(self, keys: set[str]) -> dict[str, tuple[str, str]]:
        """Same lookup, but carrying the entity type with each value.

        The caller has to put the restored value back in the case the token was
        standing in, and WHICH inflector does that depends on what the value is.
        Guessing from the string is where «Санкт-Петербурге» became
        «Санкт-Петербургее»: the person inflector read a city as a run of name
        parts and inflected one that was already in the target case. The type is
        recorded at mint time and costs one more column in a query that already
        runs — there is no reason to infer it."""
        return self._lookup_typed("name_key", keys)

    def _lookup_typed(self, column: str, keys: set[str]) -> dict[str, tuple[str, str]]:
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
                    f"SELECT {column}, entity_type, "
                    f"CASE WHEN entity_type='NAME' THEN canonical ELSE original END "
                    f"FROM tokens WHERE customer=? AND {column} IN ({placeholders})",
                    (self._customer, *chunk),
                ).fetchall()
            found.update({row[0]: (row[1], row[2]) for row in rows})
        return found

    def resolve_name_keys(self, keys: set[str]) -> dict[str, str]:
        """Resolve NAME tokens the model INFLECTED, by case-invariant key.

        The second line of defence, and the reason a fake no longer reaches a
        customer's tool when the model writes `Руслану Хвостову` instead of the
        nominative it was handed. Phones have had this since the digit-signature
        reindex; names went without it, which is precisely where the silent
        failure lived.
        """
        return self._lookup("name_key", keys)

    def _lookup(self, column: str, keys: set[str]) -> dict[str, str]:
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
                    f"SELECT {column}, CASE WHEN entity_type='NAME' THEN canonical ELSE original END FROM tokens "
                    f"WHERE customer=? AND {column} IN ({placeholders})",
                    (self._customer, *chunk),
                ).fetchall()
            found.update({row[0]: row[1] for row in rows})
        return found
