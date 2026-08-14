"""The Ed25519 signing key of the licensing server.

One key, held only by us; its public half is compiled into the customer's binary.
It answers "did Obscura make this bundle" — see `obscura/bundle.py` for why that
question is separate from "who may open it".

The private key is loaded from the environment as base64 raw bytes, never from a
file in the image: the licensing server is the one component that runs on our
own infrastructure, so its secret comes from the platform's secret store.

`OBSCURA_SIGNING_KEY` absent is allowed ONLY for a local stand, where a fresh
ephemeral key is generated and its public half printed — a stand must be
reproducible from nothing. In that mode the server says so loudly, because a
production instance that silently regenerated its key would invalidate every
deployed binary's compiled-in public key at once.
"""

import base64
import logging
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from obscura.bundle import decode_public_key

_log = logging.getLogger("licensing.keys")

# Re-exported so the server and the tooling have one name for it; the parser
# itself lives in obscura/bundle.py because the ENGINE needs it and cannot import
# anything from this package.
decode_public = decode_public_key


def encode_private(key: Ed25519PrivateKey) -> str:
    raw = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    return base64.b64encode(raw).decode("ascii")


def encode_public(key: Ed25519PublicKey) -> str:
    raw = key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def decode_public(encoded: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(encoded))


def load_signing_key() -> Ed25519PrivateKey:
    encoded = os.environ.get("OBSCURA_SIGNING_KEY", "")
    if encoded:
        return Ed25519PrivateKey.from_private_bytes(base64.b64decode(encoded))
    key = Ed25519PrivateKey.generate()
    _log.warning(
        "OBSCURA_SIGNING_KEY is not set — generated an EPHEMERAL signing key. "
        "Every binary compiled against a different public key will reject this "
        "server's leases. Public key: %s", encode_public(key.public_key()),
    )
    return key
