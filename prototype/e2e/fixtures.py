"""The personal data the e2e gates push through a real instance.

Two roles, and they are different:

  * `PII_PAYLOAD` is what a customer's agent would actually send. Every gate that
    checks for a leak greps container logs, request bodies and the filesystem for
    each of these VALUES. They are chosen to span the recognizer families, so a
    leak in any one layer shows up.

  * `marker_surname()` is a rare surname that exists ONLY in the leased
    dictionary — not in the seed list, not in the code. It is the tracer for
    "did the bundle touch the disk": finding it anywhere in the container's
    filesystem or in an expired process's memory means the assets escaped.
    It is read out of the bundle source rather than hard-coded, so it cannot
    silently stop being a bundle-only word.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from licensing import assets_source  # noqa: E402
from licensing.pack import _load_dictionary  # noqa: E402

PII_PAYLOAD: dict[str, str] = {
    "name": "Иван Петров",
    "phone": "+7 999 123-45-67",
    "email": "ivan.petrov@example.ru",
    "snils": "112-233-445 95",
    "inn": "500100732259",
    "card": "4111 1111 1111 1111",
    "passport": "45 09 123456",
    "address": "улица Ленина 5, кв 12",
}

MESSAGE = (
    f"Клиент {PII_PAYLOAD['name']}, телефон {PII_PAYLOAD['phone']}, "
    f"почта {PII_PAYLOAD['email']}, СНИЛС {PII_PAYLOAD['snils']}, "
    f"ИНН {PII_PAYLOAD['inn']}, карта {PII_PAYLOAD['card']}, "
    f"паспорт {PII_PAYLOAD['passport']}, доставьте на {PII_PAYLOAD['address']}"
)


def mask_body(org_id: str) -> dict[str, object]:
    return {"org_id": org_id, "messages": [{"role": "user", "content": MESSAGE}]}


def mask_body_variant(org_id: str, index: int) -> dict[str, object]:
    """A request that does real detection work, for load and latency measurement.

    Two things are deliberate. The content VARIES, so the content cache cannot
    answer it — caching is the thing under test elsewhere, and here it would turn
    a masking benchmark into a dictionary lookup. The org_id does NOT vary,
    because a new org means a new Vault and a new SQLite connection per request:
    that measures store creation, not masking, and leaks a connection per call."""
    return {
        "org_id": org_id,
        "messages": [{"role": "user", "content": f"{MESSAGE} (обращение №{index})"}],
    }


def marker_surname() -> str:
    """A surname that lives only in the leased bundle.

    Picked deterministically from the far end of the dictionary and checked
    against the seed lists, so it can never be a word the engine already knows.
    Long, to make a false grep hit essentially impossible."""
    seed = set(assets_source.SEED_FIRST_NAMES) | set(assets_source.DIMINUTIVES)
    surnames = _load_dictionary("surnames.txt")
    candidates = [word for word in surnames if len(word) >= 12 and word not in seed]
    if not candidates:
        raise RuntimeError("no bundle-only marker surname found — the tracer for "
                           "'assets on disk' would be meaningless")
    return candidates[len(candidates) // 2]


def leak_values() -> list[str]:
    """Everything that must never appear in a log, on disk, or on the wire out."""
    return list(PII_PAYLOAD.values()) + [marker_surname()]
