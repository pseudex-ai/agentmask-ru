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
from pseudex import morph_names, morph_places, spoken, translit
from pseudex.spoken import (email_from_words, numeral_runs,
                            plate_from_words, run_to_digits)
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
    # Added 04.09: the entries that also pass `survives_round_trip` alone.
    "Бобров", "Кудрявцев", "Мухин", "Титов", "Уваров", "Якушев", "Крылов", "Фролов",
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
    """Region «00», valid check digits, the ORIGINAL's length (10 or 12)."""
    twelve = len("".join(ch for ch in original if ch.isdigit())) == 12
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


def _fake_card() -> str:
    """MII «0», Luhn-valid — no issuer exists under that first digit."""
    for _ in range(50):
        body = "0" + _rand_digits(14)
        body += _luhn_check_digit(body)
        if validate_luhn(body):
            return f"{body[:4]} {body[4:8]} {body[8:12]} {body[12:]}"
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

_SPOKEN_WORD = re.compile(r"[А-Яа-яЁё]{2,}")
# Типы, у которых канонизация даёт САМО ЗНАЧЕНИЕ в нормальной форме, а не ключ
# для поиска. Для них и только для них аргументу отдаётся канон.
# DOB is here for the same reason as a phone: a birth date said aloud is a
# phrase the tool cannot store, and the agent's schema asks for a date.
_CANONICAL_IS_THE_VALUE = frozenset(_NUMERIC_TYPES) | {"EMAIL", "PLATE", "DOB"}


def looks_dictated(original: str, canonical: str) -> bool:
    """Написанное — это ФРАЗА, произнесённая вслух, а не значение.

    Продиктованный идентификатор — всегда прогон русских слов: «восемь девятьсот
    двадцать шесть…», «ситникова собака мэйл точка ру», «а двести шестьдесят три
    о ка регион шестьдесят шесть». Записанное значение таким не бывает ни у
    одного типа, кроме имени, — а имя решается отдельной веткой выше.

    Двух слов достаточно и меньше нельзя: одно кириллическое слово встречается
    в написанном адресе («Ленина 14»), а два подряд — только в диктовке.
    """
    if original == canonical:
        return False
    return len(_SPOKEN_WORD.findall(original)) >= 2


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
    if (for_tool and entity_type in _CANONICAL_IS_THE_VALUE
            and looks_dictated(original or "", canonical or "")):
        return canonical
    # A STREET THE CUSTOMER MISTYPED REACHES THE TOOL AS THE REGISTER SPELLS
    # IT, AND ONLY THE TOOL. Without the gateway the agent silently repairs
    # «мончгорская» to «Мончегорская» and the CRM finds the address; with the
    # gateway it is shown a clean substitute, has nothing to repair, and the
    # customer's literal words reach the tool — a street that does not exist.
    # 42 of the 103 street/address conflicts on the 06.09 live run, and in
    # every one of them BOTH control arms had repaired it, so this is the
    # reference behaviour rather than a policy of ours.
    #
    # IN PROSE THE CUSTOMER KEEPS HIS OWN WORDS. Repeating his address back
    # corrected is a different act from filling a form with it: one is the
    # agent talking to him, the other is the agent acting for him. The three
    # signals that make the repair safe are in `address.register_spelling`.
    if for_tool and entity_type == "LOC" and original:
        from pseudex.address import repair_street
        return repair_street(original)
    return original


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
_DATE_PARTS = re.compile(r"(?:^|\D)(\d{1,4})[.\-/ ](\d{1,2})[.\-/ ](\d{1,4})(?:\D|$)")


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
    return rendered


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
    if not head:
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
        out = f"{out} {secrets.randbelow(_FAKE_HOUSE_MAX) + 1}"
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


@functools.lru_cache(maxsize=2)
def _round_trip_last_names(gender: str) -> tuple[str, ...]:
    """The surnames whose form in this gender resolves back from every case
    when it stands ALONE — the feminine invariant list, and the masculine
    entries of the pool that pass the same check."""
    if gender == "femn":
        return _invariant_last_names()
    usable = tuple(s for s in _FAKE_LAST + _FAKE_LAST_INVARIANT
                   if morph_names.survives_round_trip(s, "masc"))
    if len(usable) < 12:
        raise RuntimeError(f"only {len(usable)} masculine surname(s) survive a lone round trip — widen _FAKE_LAST")
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
        # …AND THE MASCULINE HALF NEEDS THE SAME CHECK. A masculine surname
        # that failed its lone round trip twelve times fell through to «Имя
        # Фамилия», and the CRM card's `last_name` leaf was shown a two-word
        # person (live v4, chain-014).
        surnames = (_round_trip_last_names(resolved)
                    if plan == ("surn",) else _FAKE_LAST)
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
        return _fake_card()
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
            rf"|(?i:{abbrs})\.?\s{name}"           # ул. Тополиная
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
    return (rf"(?:(?:{city}), )?{head}(?:,? \d{{1,3}})?"
            rf"(?:,? (?i:корп|кор|стр|строение|литер)\.? ?\d{{1,3}})?"
            rf"(?:,? (?i:подъезд|под)\.? ?\d{{1,3}})?(?:,? кв\.? ?\d{{1,3}})?")


LOC_TOKEN_PATTERN = _loc_token_pattern()

# Where the question «is this string our own substitute?» is asked. Named here
# so the two entry points, the vault and the docs use ONE spelling of each.
PSEUDONYM_SCOPES = ("conversation", "customer")

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
        # WHOSE SUBSTITUTE THIS IS, asked at conversation scope by default. See
        # `with_pseudonym_scope` for the one reason a host widens it (agent
        # memory) and for the price of widening.
        self._pseudonym_scope = "conversation"
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
            "has_city INTEGER NOT NULL DEFAULT 1, "
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
        self._migrate_place_has_city()
        self._migrate_fold_key()
        self._migrate_minted_in()
        self._migrate_extends()
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

    def tokenize(self, value: str, entity_type: str) -> str:
        with stage("vault.tokenize"):
            return self._tokenize(value, entity_type)

    def tokenize_person(self, value: str, cases: tuple[str, ...]) -> str:
        """`tokenize` for a NAME whose sentence says which cases it may be in
        (`detect.NameSpan`); the key and the substitute's gender follow one
        reading of the phrase instead of two votes."""
        return self._tokenize(value, "NAME", cases)

    def _tokenize(self, value: str, entity_type: str, cases: tuple[str, ...] = ()) -> str:
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
                    # none of those strings is the token. ONE row per word, the
                    # FOLDED default rendering: the four standards' spellings
                    # were indexed here and the model wrote a fifth
                    # («Meshcheryakova»), which reached the tool unresolved.
                    # Every rendering folds to this key (`translit.fold`), and
                    # the lookup folds what the model wrote.
                    if translit.is_cyrillic_word(word):
                        fake_parts.add(translit.folded(word))
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
        # ОБЛАСТЬ РАЗГОВОРА ОБЯЗАТЕЛЬНА ЗДЕСЬ, а не желательна. Целая подмена
        # уникальна, и разрешать её по всему клиенту безопасно: назвать её мог
        # только тот, кому мы её отдали. ФРАГМЕНТ не уникален — «Полевая 35»
        # выглядит одинаково у всех, — и без области диалог B получал адрес,
        # отчеканенный в диалоге A. Это ровно то раскрытие, ради запрета
        # которого область и заведена.
        scope = " AND (k.minted_in=? OR k.minted_in IS NULL OR k.minted_in='')"
        with self._lock:
            owners: list[set[str]] = []
            for part in parts:
                rows = self._conn.execute(
                    "SELECT t.token FROM token_parts AS t "
                    "JOIN tokens AS k ON k.customer=t.customer AND k.token=t.token "
                    "WHERE t.customer=? AND t.part=? AND k.entity_type='LOC'"
                    + (scope if self._conversation else ""),
                    (self._customer, part, self._conversation)
                    if self._conversation else (self._customer, part),
                ).fetchall()
                if not rows:
                    return None
                owners.append({row[0] for row in rows})
        common = set.intersection(*owners)
        if len(common) == 1:
            return next(iter(common))
        if not common:
            return None
        # Two owners that are ONE place — the short mention and the full one
        # grown from it — answer with the fullest; two real places refuse.
        with self._lock:
            return self._one_identity(common)

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
        scope = " AND (k.minted_in=? OR k.minted_in IS NULL OR k.minted_in='')"
        with self._lock:
            owners: list[set[str]] = []
            for part in stems:
                rows = self._conn.execute(
                    "SELECT t.token FROM token_parts AS t "
                    "JOIN tokens AS k ON k.customer=t.customer AND k.token=t.token "
                    "WHERE t.customer=? AND t.part=? AND k.entity_type='LOC'"
                    + (scope if self._conversation else ""),
                    (self._customer, part, self._conversation) if self._conversation else (self._customer, part),
                ).fetchall()
                if not rows:
                    return None
                owners.append({row[0] for row in rows})
            common = set.intersection(*owners)
            if len(common) < 2:
                return next(iter(common)) if common else None
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
        scope = " AND (k.minted_in=? OR k.minted_in IS NULL OR k.minted_in='')"
        with self._lock:
            rows = self._conn.execute(
                "SELECT k.entity_type, k.canonical, k.original FROM token_parts AS t "
                "JOIN tokens AS k ON k.customer=t.customer AND k.token=t.token "
                "WHERE t.customer=? AND t.part=? AND k.entity_type IN ('DOB','DATE')"
                + (scope if self._conversation else "") + " LIMIT 3",
                (self._customer, reading, self._conversation) if self._conversation
                else (self._customer, reading),
            ).fetchall()
        values = {_pick_value(row[0], row[1], row[2], for_tool) for row in rows}
        return next(iter(values)) if len(values) == 1 else None

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
        """
        digits = "".join(ch for ch in fragment if ch.isdigit())
        if len(digits) < 2:
            return None
        scope = " AND (minted_in=? OR minted_in IS NULL OR minted_in='')"
        with self._lock:
            rows = self._conn.execute(
                "SELECT token, digits, entity_type, canonical, original "
                "FROM tokens WHERE customer=? AND digits IS NOT NULL "
                "AND length(digits) > ? AND instr(digits, ?) > 0"
                + (scope if self._conversation else ""),
                (self._customer, len(digits), digits, self._conversation)
                if self._conversation else (self._customer, len(digits), digits),
            ).fetchall()
        # THE CUE NARROWS THE QUESTION. «контрольное число 77» is the END of a
        # СНИЛС, «серия 4509» the START of a passport, «последние четыре цифры
        # телефона» the end of a phone — and a two-digit fragment read against
        # every substitute's digits finds three owners and refuses, while read
        # against one type at one position it has exactly one.
        found: list[tuple[str, str]] = []
        for _token, token_digits, row_type, canonical, original in rows:
            if entity_type is not None and row_type != entity_type:
                continue
            value = _pick_value(row_type, canonical or "", original or "", True)
            real = "".join(ch for ch in value if ch.isdigit())
            if len(real) != len(token_digits):
                # Разной длины — смещение не переносится, и угадывать нельзя.
                continue
            start = token_digits.find(digits)
            while start >= 0:
                at_end = start + len(digits) == len(token_digits)
                if (position is None or (position == "end" and at_end)
                        or (position == "start" and start == 0)):
                    found.append((real[start:start + len(digits)], row_type))
                start = token_digits.find(digits, start + 1)
        unique = {pair for pair in found}
        return next(iter(unique)) if len(unique) == 1 else None

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
        if len(shared) == 1:
            return next(iter(shared))
        if not shared:
            return None
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
            if stored == part or not _street_stems_match(_street_stem(stored), stem):
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
        """The substitute for a CITY-BEARING address this conversation already
        holds with the same city, street and house — written another way.

        «Самара, Луговая 10» from the customer and «Самарская область, г
        Самара, ул Луговая, д 10» back from the directory are one place, and
        the canonical keeps them apart on purpose: the type word is part of the
        identity («Ленинский проспект» is not «Ленинская улица»), so a key
        that dropped it would merge two streets. What it may not do is mint a
        second substitute for one place — the model then compares the address
        it asked about with a different fake and answers «не найден» (live v4,
        `compare`: 29 of 42 triples).

        Same discipline as every link here: exactly one owner on that street
        and house in this conversation, AND the same settlement — a different
        city on the same street and house is a different place and gets its own
        substitute.
        """
        if not self._conversation or not shape.get("has_city"):
            return None
        part = morph_places.street_house_key(value)
        if not part:
            return None
        rows = self._place_rows(part, has_city=1)
        # THE WHOLE IDENTITY MINUS THE TYPE WORD: settlement, street stem and
        # every number as written. The short key drops the house litera on
        # purpose (a short mention may omit it), and read alone it linked the
        # register's NEIGHBOUR — «д 10А» to «д 10» — into one substitute.
        wanted = _place_identity(canonical)
        same = [token for owner_canonical, token in rows
                if _same_house(_place_identity(owner_canonical), wanted)]
        if len(same) != 1:
            return None
        return same[0], same[0]

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
        key = morph_places.street_house_key(value)
        if not key:
            return False
        with self._lock:
            rows = self._conn.execute(
                "SELECT token FROM tokens WHERE customer=? AND entity_type='LOC' "
                "AND minted_in=?",
                (self._customer, self._conversation),
            ).fetchall()
        return any(morph_places.street_house_key(token) == key for (token,) in rows)

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
        token_gender = morph_names.detect_gender(short_token)
        if token_gender in ("masc", "femn") and gender in ("masc", "femn") and token_gender != gender:
            return None
        known = {w.casefold() for w in short_canonical.split()}
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
                elif kind == "patr":
                    built.append(secrets.choice(patronymics))
                elif kind == "surn":
                    surname = secrets.choice(_FAKE_LAST)
                    built.append(morph_names.feminine_surname(surname) if resolved == "femn" else surname)
                elif kind == "init":
                    built.append(secrets.choice(_INITIAL_LETTERS) + ".")
                else:
                    built.append(secrets.choice(_first_names_by_gender()[resolved]))
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

    def _migrate_place_has_city(self) -> None:
        """Whether the indexed address named a city. Rows written before the
        column were city-bearing by construction, so the default is 1."""
        columns = [row[1] for row in
                   self._conn.execute("PRAGMA table_info(place_parts)").fetchall()]
        if "has_city" in columns:
            return
        self._conn.execute(
            "ALTER TABLE place_parts ADD COLUMN has_city INTEGER NOT NULL DEFAULT 1")
        self._conn.commit()

    def _migrate_extends(self) -> None:
        """Which substitute this one was grown from — the short mention's token
        for a full address, the two-word name's for a three-word one. NULL for
        every row minted before the column and for every fresh mint; the chain
        is what lets a fragment resolve when two tokens share its parts."""
        columns = [row[1] for row in
                   self._conn.execute("PRAGMA table_info(tokens)").fetchall()]
        if "extends" not in columns:
            self._conn.execute("ALTER TABLE tokens ADD COLUMN extends TEXT")
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

    def detokenize_many(self, tokens: set[str],
                        for_tool: bool = False) -> dict[str, str]:
        """Resolve a batch of candidate tokens in indexed point queries. Unknown
        candidates are simply absent from the result — the caller leaves that text
        untouched. This is what keeps the response leg independent of vault size."""
        return self._lookup("token", tokens, for_tool)

    def resolve_digit_signatures(self, signatures: set[str],
                                 for_tool: bool = False) -> dict[str, str]:
        """Resolve numeric tokens by digit signature, for the case where the model
        reformatted one so it no longer matches its minted shape. A full-signature
        hit wins over a phone last-10 hit (the caller asks in that order)."""
        resolved = self._lookup("digits10", signatures, for_tool)
        resolved.update(self._lookup("digits", signatures, for_tool))  # exact wins
        return resolved

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
                    f"SELECT {column}, {_VALUE_SQL_BOTH} "
                    f"FROM tokens WHERE customer=? AND {column} IN ({placeholders})",
                    (self._customer, *chunk),
                ).fetchall()
            found.update({row[0]: (row[1], _pick_value(row[1], row[2], row[3],
                                                       for_tool))
                          for row in rows})
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
