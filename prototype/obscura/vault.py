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

import re
import secrets
import string
import threading

from obscura.profiling import stage
from obscura.ru_pii import validate_inn, validate_luhn, validate_ogrn, validate_snils
from obscura.sqlite_setup import connect as sqlite_connect

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


def canonicalize(entity_type: str, value: str) -> str:
    """Normalize a value so equivalent forms collapse to one key."""
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


def _render_token(entity_type: str) -> str:
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
        return f"{secrets.choice(_FAKE_FIRST)} {secrets.choice(_FAKE_LAST)}"
    if entity_type == "LOC":
        # Mostly streets, because that is where the combinations are; a bare city
        # occasionally, because a bare city is what some LOC spans actually are.
        if secrets.randbelow(100) < 15:
            return secrets.choice(_FAKE_CITIES)
        return (f"улице {secrets.choice(_FAKE_STREETS)}, "
                f"{secrets.randbelow(_FAKE_HOUSE_MAX) + 1}")
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
    r"улице (?:" + "|".join(_FAKE_STREETS) + r"), \d{1,3}",        # LOC (street)
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
        self._migrate_original_form()
        # Every lookup on the response leg is an indexed point query, so
        # detokenization cost tracks the length of the answer, not the size of
        # the vault. Without these indexes each one degrades to a table scan.
        for statement in (
            "CREATE INDEX IF NOT EXISTS idx_tokens_token ON tokens (customer, token)",
            "CREATE INDEX IF NOT EXISTS idx_tokens_digits ON tokens (customer, digits)",
            "CREATE INDEX IF NOT EXISTS idx_tokens_digits10 ON tokens (customer, digits10)",
        ):
            self._conn.execute(statement)
        self._conn.commit()

    def _migrate_original_form(self) -> None:
        """Add the surface form the value was FIRST seen in.

        Canonicalization must stay, but only as the dedup key: it is what makes
        `+7 999 123-45-67` and `89991234567` resolve to one token, so the model
        sees one identity. What the TOOL receives is a different question, and
        returning the canonical form was an observable behaviour change we
        imposed — without Obscura the tool would have received exactly what the
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

    def _unique_token(self, entity_type: str) -> str:
        """Mint a token not already used for this customer.

        BOUNDED on purpose. This used to loop until it found a free token, which
        turned an exhausted pool into an unbounded hang on the request path — the
        flat five-name list meant the sixth distinct person in an org spun here
        forever. The pool is combinatorial now, but a bound still belongs here: a
        loud failure is recoverable, a hung request is not, and in a fail-closed
        gateway the 5xx is the correct outcome."""
        for _ in range(_TOKEN_MINT_ATTEMPTS):
            token = _render_token(entity_type)
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
            token = self._unique_token(entity_type)
            digits, digits10 = _digit_signatures(token, entity_type)
            # `value` (not `canonical`) — the surface form the user actually
            # typed, which is what the tool must receive. First writer wins: the
            # same person written two ways keeps the form seen first, so what the
            # tool gets is stable across turns instead of flipping with phrasing.
            self._conn.execute(
                "INSERT INTO tokens "
                "(customer, canonical, entity_type, token, digits, digits10, original) "
                "VALUES (?,?,?,?,?,?,?)",
                (self._customer, canonical, entity_type, token, digits, digits10, value),
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
        """The value as the user originally wrote it — see _migrate_original_form
        for why this is the surface form and not the canonical one."""
        with self._lock:
            row = self._conn.execute(
                "SELECT original FROM tokens WHERE customer=? AND token=?",
                (self._customer, token),
            ).fetchone()
        return row[0] if row is not None else None

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
                    f"SELECT {column}, original FROM tokens "
                    f"WHERE customer=? AND {column} IN ({placeholders})",
                    (self._customer, *chunk),
                ).fetchall()
            found.update({row[0]: row[1] for row in rows})
        return found
