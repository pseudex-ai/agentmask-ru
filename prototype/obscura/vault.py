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
import sqlite3
import string
import threading

from obscura.ru_pii import validate_inn, validate_luhn, validate_snils

_FAKE_NAMES = ["Артур Лебедев", "Полина Жукова", "Роман Тихонов", "Вера Котова", "Глеб Сорокин"]
_FAKE_PLACES = ["Зеленограде", "Светлогорске", "Приозерске", "Гатчине", "улице Берёзовой"]


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
    return candidate


def _fake_inn() -> str:
    for _ in range(50):
        candidate = _rand_digits(10)
        if not validate_inn(candidate):
            return candidate
    return candidate


def _fake_card() -> str:
    for _ in range(50):
        body = "4" + _rand_digits(15)
        if not validate_luhn(body):
            return f"{body[:4]} {body[4:8]} {body[8:12]} {body[12:]}"
    return body


def _render_token(entity_type: str) -> str:
    if entity_type == "PHONE":
        return "+79" + _rand_digits(9)
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
        return secrets.choice(_FAKE_NAMES)
    if entity_type == "LOC":
        return secrets.choice(_FAKE_PLACES)
    return f"REDACTED{secrets.token_hex(3)}"


class Vault:
    """Persistent per-customer token store (external state -> class)."""

    def __init__(self, db_path: str, customer_id: str) -> None:
        self._customer = customer_id
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tokens ("
            "customer TEXT, canonical TEXT, entity_type TEXT, token TEXT, "
            "PRIMARY KEY (customer, canonical))"
        )
        self._conn.commit()

    def tokenize(self, value: str, entity_type: str) -> str:
        canonical = canonicalize(entity_type, value)
        with self._lock:
            row = self._conn.execute(
                "SELECT token FROM tokens WHERE customer=? AND canonical=?",
                (self._customer, canonical),
            ).fetchone()
            if row is not None:
                return row[0]
            token = _render_token(entity_type)
            while self._conn.execute(
                "SELECT 1 FROM tokens WHERE customer=? AND token=?",
                (self._customer, token),
            ).fetchone() is not None:
                token = _render_token(entity_type)
            self._conn.execute(
                "INSERT INTO tokens (customer, canonical, entity_type, token) VALUES (?,?,?,?)",
                (self._customer, canonical, entity_type, token),
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
        with self._lock:
            row = self._conn.execute(
                "SELECT canonical FROM tokens WHERE customer=? AND token=?",
                (self._customer, token),
            ).fetchone()
        return row[0] if row is not None else None

    def known_tokens(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT token FROM tokens WHERE customer=?", (self._customer,)
            ).fetchall()
        return [row[0] for row in rows]

    def numeric_index(self) -> dict[str, str]:
        """Map a numeric token's digit signature -> real value, so a token the
        model REFORMATTED (phone 8XXX -> +7XXX, or separators stripped) still
        detokenizes. Phone also keys on its last 10 digits (country code varies)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT token, canonical, entity_type FROM tokens WHERE customer=? "
                "AND entity_type IN ('PHONE','CARD','SNILS','INN','PASSPORT')",
                (self._customer,),
            ).fetchall()
        index: dict[str, str] = {}
        for token, canonical, entity_type in rows:
            digits = re.sub(r"\D", "", token)
            if digits:
                index[digits] = canonical
            if entity_type == "PHONE" and len(digits) >= 10:
                index[digits[-10:]] = canonical
        return index
