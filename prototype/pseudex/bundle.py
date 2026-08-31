"""Bundle wire format: sealed to one process, signed by us.

Shared by the licensing server (which seals) and the engine (which opens), so the
two can never disagree about the format.

WHY BOTH ENCRYPTION AND A SIGNATURE — they answer different questions:

  * **age (X25519) encryption** answers "who may open this". The recipient is a
    keypair the WORKER PROCESS generated in memory at startup and never wrote
    down. A captured lease response is therefore useless anywhere else, and there
    is no portable form of the bundle to copy off the machine.

  * **Ed25519 signature** answers "who made this". age in x25519 mode does not
    authenticate the sender: anyone holding the process's public key can seal a
    bundle to it. For a product whose entire value is detection quality, a
    swapped bundle is a silent PII leak — so the engine verifies the plaintext
    hash against a signature made with a key that only we hold, and whose public
    half is compiled into the binary.

The signature covers the plaintext hash rather than the ciphertext: age
ciphertext is randomized per seal, so signing it would force a re-sign per lease
and would still say nothing about what is inside.
"""

import base64
import hashlib
import hmac
import hashlib
import json
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import (Encoding,
                                                          PublicFormat)
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pyrage import decrypt, encrypt, x25519


class BundleError(RuntimeError):
    """The bundle could not be opened, or is not ours."""


@dataclass(frozen=True)
class ProcessKey:
    """An X25519 identity that exists only in this process's memory.

    `identity` is a `pyrage.x25519.Identity` — a Rust object with no importable
    Python type to annotate, which is why this field is the one loose type in the
    module. It is never serialized, never logged and never leaves the process."""

    identity: x25519.Identity
    public: str


def generate_process_key() -> ProcessKey:
    identity = x25519.Identity.generate()
    return ProcessKey(identity=identity, public=str(identity.to_public()))


def seal(plaintext: bytes, recipient_public: str) -> str:
    """Encrypt the bundle to one process. Returns base64 for JSON transport."""
    try:
        recipient = x25519.Recipient.from_str(recipient_public)
    except Exception as error:  # pyrage raises its own type on a malformed key
        raise BundleError(f"bad recipient public key: {recipient_public!r}") from error
    return base64.b64encode(encrypt(plaintext, [recipient])).decode("ascii")


def open_sealed(sealed_b64: str, process_key: ProcessKey) -> bytes:
    try:
        return decrypt(base64.b64decode(sealed_b64), [process_key.identity])
    except Exception as error:
        raise BundleError(
            "bundle did not decrypt with this process's key — it was sealed to "
            "someone else, or the payload is corrupt"
        ) from error


def plaintext_hash(plaintext: bytes) -> str:
    return hashlib.sha256(plaintext).hexdigest()


def signing_payload(lease: dict[str, object]) -> bytes:
    """Canonical bytes covered by the signature: every field of the lease except
    the ciphertext and the signature itself. `bundle_sha256` is in there, which
    is what binds the signature to the contents."""
    covered = {key: value for key, value in lease.items()
               if key not in ("bundle", "signature")}
    return json.dumps(covered, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_lease(lease: dict[str, object], private_key: Ed25519PrivateKey) -> str:
    return base64.b64encode(private_key.sign(signing_payload(lease))).decode("ascii")


def mac_report(report: dict[str, object], secret: bytes) -> str:
    """HMAC отчёта секретом, который пришёл ЗАПЕЧАТАННЫМ на этот процесс.

    Не подпись ключом, который контейнер сам объявил: такой ключ перехватчик
    подменяет на свой в первом же обращении, и подпись начинает удостоверять
    его. Секрет он подменить не может — чтобы прочитать, надо быть получателем,
    а получатель назван в подписанной нами лизе.
    """
    return hmac.new(secret, signing_payload(report), hashlib.sha256).hexdigest()


def verify_report(report: dict[str, object], secret: bytes) -> None:
    given = report.get("signature")
    if not isinstance(given, str) or not hmac.compare_digest(
            given, mac_report({k: v for k, v in report.items()
                               if k != "signature"}, secret)):
        raise BundleError("report MAC does not verify")


def decode_public_key(encoded: str) -> Ed25519PublicKey:
    """Parse our verification key from its base64 raw form.

    Lives here, not in `licensing/`, because the ENGINE needs it and the licensing
    package never ships to a customer — importing it from the engine would drag
    the asset source into the image and defeat the whole lease."""
    try:
        return Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded))
    except Exception as error:
        raise BundleError(f"malformed verification key: {encoded[:16]!r}") from error


def verify_lease(lease: dict[str, object], public_key: Ed25519PublicKey) -> None:
    signature = lease.get("signature")
    if not isinstance(signature, str):
        raise BundleError("lease carries no signature")
    try:
        public_key.verify(base64.b64decode(signature), signing_payload(lease))
    except InvalidSignature as error:
        raise BundleError(
            "lease signature is not ours — refusing to load the bundle"
        ) from error
