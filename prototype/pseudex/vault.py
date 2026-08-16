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

import functools
import re
import secrets
import string

from pseudex import credentials
from pseudex.normalize import normalize
import threading
import time

from pseudex import morph_names, morph_places
from pseudex.profiling import stage
from pseudex.ru_pii import validate_inn, validate_luhn, validate_ogrn, validate_snils
from pseudex.sqlite_setup import connect as sqlite_connect

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
]
_FAKE_LAST = [
    "Лебедев", "Жуков", "Тихонов", "Котов", "Сорокин", "Беляев", "Гущин",
    "Ершов", "Зимин", "Карпов", "Лужин", "Мещеряков", "Наумов", "Осипов",
    "Панов", "Рыбаков", "Сазонов", "Тарасов", "Устинов", "Фомин", "Хвостов",
    "Цветков", "Чижов", "Шилов", "Щукин", "Юдин", "Яровой", "Бирюков",
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
_FAKE_CITIES = [
    "Зеленограде", "Светлогорске", "Приозерске", "Гатчине", "Кинешме",
    "Торжке", "Валдае", "Бологом", "Кимрах", "Сортавале", "Луге", "Тихвине",
    "Мышкине", "Угличе", "Плёсе", "Суздале", "Ельце", "Задонске", "Данкове",
    "Венёве", "Алексине", "Белёве", "Крапивне", "Одоеве", "Черни",
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
    import sqlite3  # noqa: PLC0415 — only this function needs it

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
    except sqlite3.Error:
        return 0
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM tokens WHERE first_seen >= ?", (since,)
        ).fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        # No vault yet, or the column predates the migration. Zero is the honest
        # answer and it under-bills, which is the safe direction.
        return 0
    finally:
        conn.close()


def canonicalize(entity_type: str, value: str) -> str:
    """Normalize a value so equivalent forms collapse to one key.

"""
    if entity_type == "PHONE":
        digits = re.sub(r"\D", "", value)
        if len(digits) == 11 and digits[0] in "78":
            digits = "7" + digits[1:]
        elif len(digits) == 10:
            digits = "7" + digits
        return "+" + digits if digits else value
    if entity_type in ("SNILS", "INN", "CARD", "PASSPORT"):
        return re.sub(r"\D", "", value)
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
        return morph_names.to_nominative(value.strip())
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
        return morph_places.to_nominative(secrets.choice(_FAKE_CITIES))
    street = morph_places.to_nominative(secrets.choice(_FAKE_STREETS))
    return f"улица {street}, {secrets.randbelow(_FAKE_HOUSE_MAX) + 1}"


def _fake_name(gender: str | None) -> str:
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
    for _ in range(12):
        first = secrets.choice(_first_names_by_gender()[resolved])
        last = secrets.choice(_FAKE_LAST)
        if resolved == "femn":
            last = morph_names.feminine_surname(last)
        candidate = f"{first} {last}"
        if morph_names.survives_round_trip(candidate, resolved):
            return candidate
    # Every attempt was unstable, which means the pool has drifted. A name that
    # cannot be recognised in its own inflected forms would be a token the model
    # can rewrite into something we never resolve — so refuse rather than mint
    # one, and let the fail-closed 5xx say so.
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
    if entity_type == "DATE":
        return f"{secrets.randbelow(28) + 1:02d}.{secrets.randbelow(12) + 1:02d}.{secrets.randbelow(40) + 1960}"
    if entity_type == "NAME":
        return _fake_name(gender)
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
    r"улица [А-ЯЁ][а-яё]+, \d{1,3}",                               # LOC (street)
    *(re.escape(value) for value in _FAKE_CITIES),                 # LOC (city)
    r"\d{2} \d{2} \d{6}",                        # DRIVER_LICENSE / VEHICLE_DOC / PASSPORT
    r"198\.1[89]\.\d{1,3}\.\d{1,3}",              # IP (RFC 2544 benchmarking)
    r"[IVX]{1,4}-[А-ЯЁ]{2} №\d{6}",               # BIRTH_CERT
    r"[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{3}", # PLATE
    r"\d{4} \d{4} \d{4} \d{4}",                   # CARD
    # Bare digit runs, LONGEST FIRST: leftmost-first alternation would otherwise
    # let \d{10} consume the head of a 20-digit account.
    r"\b\d{20}\b",                                # ACCOUNT
    r"\b\d{16}\b",                                # OMS
    r"\b\d{15}\b|\b\d{13}\b",                    # OGRN / ОГРНИП
    r"\b\d{9}\b",                                 # INTL_PASSPORT
    r"\d{3}-\d{3}-\d{3} \d{2}",                   # SNILS
    r"\d{2} \d{2} \d{6}",                         # PASSPORT
    r"\d{2}\.\d{2}\.\d{4}",                       # DATE
    r"\+79\d{9}",                                 # PHONE
    r"REDACTED[0-9a-f]{6}",                       # fallback
    r"\b\d{10}\b",                                # INN — least specific, last
]))


class Vault:
    """Persistent per-customer token store (external state -> class)."""

    def __init__(self, db_path: str, customer_id: str) -> None:
        self._customer = customer_id
        self._lock = threading.Lock()
        self._conn = sqlite_connect(db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tokens ("
            "customer TEXT, canonical TEXT, entity_type TEXT, token TEXT, "
            "PRIMARY KEY (customer, canonical))"
        )
        self._migrate_digit_signatures()
        self._migrate_name_keys()
        self._migrate_original_form()
        self._migrate_first_seen()
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
                      original: str = "") -> str:
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
                street = morph_places.to_nominative(secrets.choice(_FAKE_STREETS))
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
            if self._conn.execute(
                "SELECT 1 FROM tokens WHERE customer=? AND token=?",
                (self._customer, token),
            ).fetchone() is None:
                return token
        raise RuntimeError(
            f"exhausted the {entity_type} token pool for customer "
            f"{self._customer!r} after {_TOKEN_MINT_ATTEMPTS} attempts — widen "
            f"the pool in _render_token"
        )

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
            # The REAL person's gender decides the fake's, so the substitute
            # agrees with the sentence around it and the model leaves it alone.
            gender = (morph_names.detect_gender(value)
                      if entity_type == "NAME" else None)
            token = self._unique_token(entity_type, gender, value)
            digits, digits10 = _digit_signatures(token, entity_type)
            # `value` (not `canonical`) — the surface form the user actually
            # typed, which is what the tool must receive. First writer wins: the
            # same person written two ways keeps the form seen first, so what the
            # tool gets is stable across turns instead of flipping with phrasing.
            self._conn.execute(
                "INSERT INTO tokens "
                "(customer, canonical, entity_type, token, digits, digits10, original, "
                "first_seen, name_key) VALUES (?,?,?,?,?,?,?,?,?)",
                (self._customer, canonical, entity_type, token, digits, digits10, value,
                 time.time(),
                 name_key(token) if entity_type == "NAME"
                 else place_key(token) if entity_type == "LOC" else None),
            )
            self._conn.commit()
            return token

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
                "SELECT 1 FROM tokens WHERE customer=? AND token=? LIMIT 1",
                (self._customer, value),
            ).fetchone()
        return row is not None

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
